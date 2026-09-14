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
    ("Restaurant & Food", "restaurants"),
    ("Retail & Shopping", "retail stores and shops"),
    ("Automotive", "auto repair shops"),
    ("Health & Wellness", "health and wellness services"),
    ("Professional & Financial Services", "accounting, legal, and financial services"),
    ("Real Estate & Insurance", "real estate and insurance agencies"),
    ("Lodging & Hospitality", "hotels and lodging"),
    ("Farm & Agriculture", "farm and agriculture businesses"),
    ("Nonprofit & Civic Organization", "nonprofit organizations and civic groups"),
    ("Church & Religious Organization", "churches"),
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
    category), just bucketed under "Other" the same way any other
    un-pinnable location is elsewhere in this codebase (see
    town_or_other() in calendar_config.py) -- they just aren't findable
    by a specific-town filter."""
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
    town = city if city in config["towns"] else "Other"

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

    return listing


def _load_existing_index(business_dir):
    """(slugs, place_ids) already on file. Checked by both -- a listing's
    own file might get hand-edited after this script first wrote it (e.g.
    correcting a service-area business's "Other" town to the real one a
    person found on the business's own site, something Google's data
    just didn't have), which changes what slug build_listing() would
    compute for the exact same business today even though nothing about
    the business itself changed. place_id is stable across that, so
    matching on it too is what actually keeps a hand-corrected listing
    from getting silently re-added under its old slug next run."""
    slugs = set()
    place_ids = set()
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
    return slugs, place_ids


def main():
    if not OUTSCRAPER_API_KEY:
        print("ERROR: set OUTSCRAPER_API_KEY", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    existing_slugs, existing_place_ids = _load_existing_index(BUSINESS_DIR)

    added = 0
    for category, search_phrase in BUSINESS_QUERIES:
        query = f"{search_phrase} in {config['county_display_name']}, {config['state']}"
        print(f"Searching: {query}")
        try:
            results = run_outscraper_query(query)
        except requests.RequestException as e:
            print(f"  WARNING: request failed for {query!r}: {e}", file=sys.stderr)
            continue

        for result in results:
            listing = build_listing(result, category, config)
            if not listing:
                continue

            place_id = listing.get("place_id")
            if place_id and place_id in existing_place_ids:
                continue  # already have this business on file, possibly under a hand-corrected town/slug

            slug = f"{slugify(listing['town'])}-{slugify(listing['name'])}"
            if slug.strip("-") == "" or slug in existing_slugs:
                continue  # no usable name/town, or already have a file -- a hand-edited listing wins

            path = os.path.join(BUSINESS_DIR, f"{slug}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(listing, f, indent=2)
                f.write("\n")
            existing_slugs.add(slug)
            if place_id:
                existing_place_ids.add(place_id)
            added += 1
            print(f"  + {listing['name']} ({listing['town']})")

        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"\nAdded {added} new listing(s).")


if __name__ == "__main__":
    main()
