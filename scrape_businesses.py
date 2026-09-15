#!/usr/bin/env python3
"""
Pulls local businesses and organizations -- restaurants, shops, churches,
farms, home service trades, and everything else in BUSINESS_QUERIES --
from Google Maps via Outscraper (https://outscraper.com), a paid
third-party API that does the actual Google Maps scraping/anti-blocking
work, so this script is just "send a search, get structured results
back." Requires OUTSCRAPER_API_KEY in the environment.

Started out covering only home service trades (plumbers, electricians,
etc.) -- see git history for scrape_home_services.py if useful -- and
was broadened to every category in business_categories.

Writes one file per business straight into data/businesses/ -- same shape
and location as a listing approved by hand through admin-business.html
(see data/businesses/README.md) -- so build_business_directory.py and
docs/directory.html need no special-casing for where a listing came from.
Unlike the community calendar's manual-submission pipeline, these publish
automatically with no human approval step (see README.md's "Business &
organization directory" section for why that tradeoff was made here).

A business already on file (whether from a previous run of this script or
a manually-approved submission) is never overwritten -- a hand-edited
listing should always win over a re-scrape.

Field names and the distance filter below were both checked against a
real Outscraper pull (2026-09-14, "plumbers in Linn County, MO"): a plain
"<county>, <state>" text query is matched loosely enough that Google
returned plumbers as far off as Boonville and Warsaw, MO (90-140 miles
away), so results are only kept within MAX_DISTANCE_MILES of the county.
Results also skew heavily "service area" (a truck, no storefront) -- see
build_listing()'s docstring.

Run:
    OUTSCRAPER_API_KEY=... python scrape_businesses.py
"""
import glob
import json
import os
import re
import sys
import time
from math import atan2, cos, radians, sin, sqrt

import requests

from calendar_config import load_config

OUTSCRAPER_API_KEY = os.environ.get("OUTSCRAPER_API_KEY", "")
OUTSCRAPER_SEARCH_URL = "https://api.outscraper.com/maps/search-v3"
RESULTS_PER_QUERY = 40
POLL_ATTEMPTS = 10
POLL_INTERVAL_SECONDS = 6
REQUEST_DELAY_SECONDS = 2  # be polite between queries, not a rate-limit workaround

BUSINESS_DIR = "data/businesses"

# Roughly the geographic center of Linn County's own 8 towns (Linneus, the
# county seat, sits close to the middle of the cluster) -- used only to
# reject results a loose "<county>, <state>" text query pulls in from well
# outside the area. 30 miles comfortably covers the county itself plus
# the same neighboring-town radius already accepted elsewhere in this
# codebase (see Teter Auction's widened Macon/Chillicothe match in
# scrape_linn_county_calendar.py).
COUNTY_CENTER_LAT = 39.80
COUNTY_CENTER_LON = -93.10
MAX_DISTANCE_MILES = 30

# (directory category, what to search Google Maps for) -- category also
# becomes one of the checkboxes in docs/directory.html's filter, so keep
# these in sync with business_categories in docs/config.json. No query for
# "Home & Trade Services" (the specific trades below supersede that
# generic bucket -- it's still available for a manual submission that
# doesn't fit one of them) or "Other" (submission-form fallback only,
# never something to search Google Maps for).
BUSINESS_QUERIES = [
    ("Plumbing", "plumbers"),
    ("Electrical", "electricians"),
    ("HVAC & Cooling", "HVAC contractors"),
    ("Roofing", "roofing contractors"),
    ("Tree Service", "tree service companies"),
    ("Lawn Care & Landscaping", "lawn care and landscaping companies"),
    ("Pest Control", "pest control companies"),
    ("Handyman", "handyman services"),
    ("General Contractor", "general contractors"),
    ("Painting", "painting contractors"),
    ("Locksmith", "locksmiths"),
    ("Appliance Repair", "appliance repair services"),
    ("Fencing", "fence contractors"),
    ("Garage Door Service", "garage door repair services"),
    ("Septic, Well & Excavation", "septic, well, and excavation contractors"),
    ("Movers & Storage", "moving and storage companies"),
    ("Restaurant & Food", "restaurants"),
    ("Retail & Shopping", "retail stores and shops"),
    ("Antiques, Thrift & Secondhand", "antique malls, thrift stores, and consignment shops"),
    ("Lumber & Hardware", "lumber yards and hardware stores"),
    ("Automotive", "auto repair shops and dealerships"),
    ("Gas Stations & Convenience Stores", "gas stations and convenience stores"),
    ("Medical & Healthcare", "doctors, dentists, clinics, and hospitals"),
    ("Health & Wellness", "health and wellness services"),
    ("Salons & Personal Care", "hair salons, barbershops, and spas"),
    ("Veterinary & Pet Services", "veterinarians and pet services"),
    ("Professional & Financial Services", "accounting, legal, and financial services"),
    ("Banks & Credit Unions", "banks and credit unions"),
    ("Real Estate & Insurance", "real estate and insurance agencies"),
    ("Lodging & Hospitality", "hotels and lodging"),
    ("Farm & Agriculture", "farm supply stores, feed stores, and farm equipment dealers"),
    ("Nonprofit & Civic Organization", "nonprofit organizations and civic groups"),
    ("Church & Religious Organization", "churches"),
    ("Government & Public Services", "city hall, post office, and government offices"),
    ("Funeral Homes & Cemeteries", "funeral homes"),
    ("Auctions & Estate Sales", "auction companies and estate sales"),
    ("Education & Childcare", "schools and daycare centers"),
    ("Arts, Recreation & Entertainment", "arts and recreation venues"),
]


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _get(result, *keys):
    """First truthy value found in RESULT across a few plausible key
    spellings -- Outscraper's own schema for a field isn't pinned down
    with certainty here, see the module docstring."""
    for key in keys:
        value = result.get(key)
        if value:
            return value
    return None


def _distance_miles(lat, lon):
    earth_radius_miles = 3958.8
    lat1, lon1, lat2, lon2 = map(radians, [COUNTY_CENTER_LAT, COUNTY_CENTER_LON, lat, lon])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return earth_radius_miles * 2 * atan2(sqrt(a), sqrt(1 - a))


def _flatten_results(payload):
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(data, list):
        return []
    results = []
    for item in data:
        if isinstance(item, list):
            results.extend(item)
        elif isinstance(item, dict):
            results.append(item)
    return results


def run_outscraper_query(query):
    """Runs one Google Maps search via Outscraper and returns a flat list
    of raw result dicts. A query Outscraper can't finish inline comes
    back as a "Pending" job with a location to poll instead of results
    -- handled here so callers don't need to care either way."""
    headers = {"X-API-KEY": OUTSCRAPER_API_KEY}
    resp = requests.get(
        OUTSCRAPER_SEARCH_URL,
        headers=headers,
        params={"query": query, "limit": RESULTS_PER_QUERY, "async": "false"},
        timeout=60,
    )
    resp.raise_for_status()
    payload = resp.json()

    if isinstance(payload, dict) and payload.get("status") == "Pending":
        results_url = payload.get("results_location")
        if not results_url:
            print(f"  WARNING: {query!r} came back Pending with no results_location, skipping", file=sys.stderr)
            return []
        for _ in range(POLL_ATTEMPTS):
            time.sleep(POLL_INTERVAL_SECONDS)
            poll_resp = requests.get(results_url, headers=headers, timeout=30)
            poll_resp.raise_for_status()
            payload = poll_resp.json()
            if isinstance(payload, dict) and payload.get("status") == "Success":
                break
        else:
            print(f"  WARNING: {query!r} still pending after {POLL_ATTEMPTS} polls, skipping", file=sys.stderr)
            return []

    return _flatten_results(payload)


def build_listing(result, category, config):
    """Returns a listing dict in the same shape as a manually-approved
    data/businesses/*.json file, or None if RESULT shouldn't become one
    (permanently/temporarily closed, or missing even a name).

    Confirmed against a real Outscraper response (2026-09-14, "plumbers in
    Linn County, MO"): roughly 60% of home-service results are "service
    area" businesses (a truck, no public storefront) with no address or
    city at all, just a lat/long and a service radius -- Google itself
    doesn't tie them to a town. Those still become listings (dropping a
    business for every service-area plumber/electrician would gut this
    category), just bucketed under "Linn County" -- true (everything here
    already passed the distance filter above) even when the specific town
    isn't -- rather than a fixed town or the unhelpful word "Other". Still
    findable, just not by a specific-town filter, unless someone later
    resolves the real town by hand (see data/businesses/README.md)."""
    status = (result.get("business_status") or "").upper()
    if status and status != "OPERATIONAL":
        return None

    name = (_get(result, "name") or "").strip()
    if not name:
        return None

    lat, lon = result.get("latitude"), result.get("longitude")
    if lat is not None and lon is not None and _distance_miles(lat, lon) > MAX_DISTANCE_MILES:
        return None

    city = (_get(result, "city") or "").strip()
    town = city if city in config["towns"] else "Linn County"

    listing = {
        "name": name,
        "category": category,
        "town": town,
        # Bookkeeping only -- build_business_directory.py whitelists which
        # fields reach the public docs/businesses.json, so these never
        # show up on the site itself. Kept so a stale/incorrect scraped
        # listing can be tracked back to its source, and so a future
        # "re-scrape and refresh" pass could match on place_id instead of
        # name+town.
        "source": "google_maps",
    }

    # Review count: used both to pick a winner when the same real
    # business turns up as two separate Google listings (see
    # _dedupe_against_existing()) and, now, shown on the public site
    # alongside rating -- never the review text itself.
    reviews = result.get("reviews")
    if isinstance(reviews, (int, float)):
        listing["reviews"] = int(reviews)

    rating = result.get("rating")
    if isinstance(rating, (int, float)):
        listing["rating"] = round(float(rating), 1)

    # Direct link to a Google-hosted photo -- publicly hotlinkable, no API
    # key or proxying needed, same as any other Google Maps image URL.
    photo = (_get(result, "photo") or "").strip()
    if photo:
        listing["photo"] = photo

    # "address" is already the full "street, city, state zip" string when
    # present, not just a street -- no reassembly needed.
    address = (_get(result, "address", "full_address", "formatted_address") or "").strip()
    if address:
        listing["address"] = address

    phone = (_get(result, "phone", "phone_number", "international_phone_number") or "").strip()
    if phone:
        listing["phone"] = phone

    website = (_get(result, "website", "site", "domain") or "").strip()
    if website:
        listing["website"] = website

    email = _get(result, "email_1", "email")
    if isinstance(email, list):
        email = email[0] if email else None
    if email:
        listing["email"] = str(email).strip()

    place_id = _get(result, "place_id", "google_id")
    if place_id:
        listing["place_id"] = str(place_id)

    # Google's own blurb for the business, when it has one (chains tend
    # to; small independent listings often don't) -- shown on the site
    # the same as a manually-submitted description.
    description = (_get(result, "description") or "").strip()
    if description:
        listing["description"] = description

    # Search-only, never shown on the card: Google's own "subtypes" (a
    # comma-separated list -- a business can be tagged more than one way
    # on Google even though it only gets one category here, e.g. Tractor
    # Supply Co is "Animal feed store, Farm shop, ... Hardware store,
    # ... Pet store") plus "reviews_tags" (words Google surfaces because
    # reviewers actually used them, e.g. "farm supplies", "workwear").
    # This is what lets a search for "clothing" surface a farm store that
    # also carries Carhartt, without needing a second visible category.
    keywords = []
    subtypes = result.get("subtypes")
    if isinstance(subtypes, str):
        keywords.extend(s.strip() for s in subtypes.split(",") if s.strip())
    reviews_tags = result.get("reviews_tags")
    if isinstance(reviews_tags, list):
        keywords.extend(str(t).strip() for t in reviews_tags if str(t).strip())
    if keywords:
        # Dedupe case-insensitively, keep first-seen casing.
        seen = set()
        deduped = []
        for kw in keywords:
            key = kw.lower()
            if key not in seen:
                seen.add(key)
                deduped.append(kw)
        listing["keywords"] = deduped

    return listing


def _is_multi_location_file(path):
    """True if PATH is a hand-merged multi-town listing (has "towns"
    instead of a single "town" -- see data/businesses/README.md).
    Auto-dedup treats these as always-winning rather than something a
    fresh single-location duplicate can delete/replace, since deleting
    the file would lose every other town on it, not just the one that
    matched."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return isinstance(json.load(f).get("towns"), list)
    except (OSError, json.JSONDecodeError):
        return False


def normalize_business_name(name):
    """Loose match key for spotting the same real business listed twice
    under two separate Google profiles (different place_id, sometimes a
    slightly different name) -- e.g. "Botts & Tye Air Conditioning and
    Heating" and "Botts & Tye Air Conditioning & Heating, Brookfield, MO"
    turned up as two distinct scrape results for the real Chillicothe
    business. Lowercased, punctuation and common entity suffixes
    stripped."""
    text = re.sub(r"[^a-z0-9 ]+", " ", name.lower())
    for suffix in (" llc", " inc", " incorporated", " corp", " co", " ltd", " lc", " pc"):
        text = text.replace(suffix, " ")
    return re.sub(r"\s+", " ", text).strip()


def _load_existing_index(business_dir):
    """(slugs, place_ids, by_name_town) already on file.

    slugs/place_ids are checked on every new result -- a listing's own
    file might get hand-edited after this script first wrote it (e.g.
    correcting a service-area business's generic "Linn County" town to
    the real one a person found on the business's own site, something
    Google's data just didn't have), which changes what slug
    build_listing() would compute for the exact same business today even
    though nothing about the business itself changed. place_id is stable
    across that, so matching on it too is what actually keeps a
    hand-corrected listing from getting silently re-added under its old
    slug next run.

    by_name_town maps (normalize_business_name(name), town) -> (path,
    reviews) -- a *different* place_id under a name/town that matches an
    existing listing is (per Kevin) almost always the same real business
    on a duplicate Google profile rather than two actual businesses, so
    main() uses this to keep only whichever one has more reviews instead
    of publishing both.

    A multi-town listing (a "towns" array + "locations" instead of a
    single "town" -- see data/businesses/README.md) contributes every one
    of its locations' place_id and (name, town) here too, keyed to the
    one shared file -- otherwise a future run would rediscover, say,
    Casey's in Brookfield under its old standalone place_id and add it
    back as a second, separate, un-merged file."""
    slugs = set()
    place_ids = set()
    by_name_town = {}
    for path in glob.glob(os.path.join(business_dir, "*.json")):
        slugs.add(os.path.splitext(os.path.basename(path))[0])
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        place_id = data.get("place_id")
        if place_id:
            place_ids.add(str(place_id))

        name = data.get("name")
        if isinstance(data.get("towns"), list):
            for loc in data.get("locations") or []:
                if not isinstance(loc, dict):
                    continue
                if loc.get("place_id"):
                    place_ids.add(str(loc["place_id"]))
                if name and loc.get("town"):
                    by_name_town[(normalize_business_name(name), loc["town"])] = (path, data.get("reviews") or 0)
        else:
            town = data.get("town")
            if name and town:
                by_name_town[(normalize_business_name(name), town)] = (path, data.get("reviews") or 0)
    return slugs, place_ids, by_name_town


def _run_query(query, category, config, state):
    """Runs one Outscraper search and writes/replaces files for whatever
    in it is new -- shared by both the county-wide and the per-town
    passes in main() so they go through identical filtering/dedup logic.
    Mutates STATE's index sets/dict in place; returns (added, replaced)
    counts for this query alone."""
    print(f"Searching: {query}")
    try:
        results = run_outscraper_query(query)
    except requests.RequestException as e:
        print(f"  WARNING: request failed for {query!r}: {e}", file=sys.stderr)
        return 0, 0

    added = replaced = 0
    for result in results:
        listing = build_listing(result, category, config)
        if not listing:
            continue

        place_id = listing.get("place_id")
        if place_id and place_id in state["place_ids"]:
            continue  # already have this business on file, possibly under a hand-corrected town/slug

        # A different place_id under a name/town that already matches
        # something on file -- almost always a duplicate Google profile
        # for the same real business (see normalize_business_name()),
        # not two real businesses, or the same business turning up again
        # in a different pass (county-wide vs. per-town) of this same
        # run. Keep whichever has more reviews.
        name_town_key = (normalize_business_name(listing["name"]), listing["town"])
        dupe = state["by_name_town"].get(name_town_key)
        if dupe:
            dupe_path, dupe_reviews = dupe
            if _is_multi_location_file(dupe_path):
                continue  # a merged multi-town listing is curated by hand -- never auto-replaced
            if listing.get("reviews", 0) <= dupe_reviews:
                continue  # existing listing has as many or more reviews -- keep it, skip this one
            os.remove(dupe_path)
            state["slugs"].discard(os.path.splitext(os.path.basename(dupe_path))[0])
            print(f"  ~ {listing['name']}: replacing {os.path.basename(dupe_path)} ({dupe_reviews} reviews) with {listing.get('reviews', 0)}-review duplicate")
            replaced += 1

        slug = f"{slugify(listing['town'])}-{slugify(listing['name'])}"
        if slug.strip("-") == "" or (not dupe and slug in state["slugs"]):
            continue  # no usable name/town, or already have a file -- a hand-edited listing wins

        path = os.path.join(BUSINESS_DIR, f"{slug}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(listing, f, indent=2)
            f.write("\n")
        state["slugs"].add(slug)
        if place_id:
            state["place_ids"].add(place_id)
        state["by_name_town"][name_town_key] = (path, listing.get("reviews", 0))
        added += 1
        print(f"  + {listing['name']} ({listing['town']})")

    time.sleep(REQUEST_DELAY_SECONDS)
    return added, replaced


def main():
    if not OUTSCRAPER_API_KEY:
        print("ERROR: set OUTSCRAPER_API_KEY", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    slugs, place_ids, by_name_town = _load_existing_index(BUSINESS_DIR)
    state = {"slugs": slugs, "place_ids": place_ids, "by_name_town": by_name_town}

    added = replaced = 0
    for category, search_phrase in BUSINESS_QUERIES:
        # A single "<phrase> in Linn County, MO" search sounds like it
        # should cover the whole county, but Google's relevance ranking
        # for a broad area query buries small-town results -- confirmed
        # 2026-09-15: a plain county-wide "churches" search surfaced only
        # 4 of Marceline's real 9 churches. Querying each town by name
        # too (Google resolves a specific town far more completely) is
        # what actually gets full coverage; the county-wide pass on top
        # still catches genuine service-area/regional businesses that
        # aren't pinned to one town at all. A business found by more than
        # one of these passes is caught by the same place_id/name+town
        # dedup as a re-run of the whole script, so this costs extra
        # Outscraper queries but never produces duplicate listings.
        county_query = f"{search_phrase} in {config['county_display_name']}, {config['state']}"
        a, r = _run_query(county_query, category, config, state)
        added += a
        replaced += r

        for town in config["towns"]:
            town_query = f"{search_phrase} in {town}, {config['state']}"
            a, r = _run_query(town_query, category, config, state)
            added += a
            replaced += r

    print(f"\nAdded {added} new listing(s), replaced {replaced} duplicate(s) with a higher-reviewed profile.")


if __name__ == "__main__":
    main()
