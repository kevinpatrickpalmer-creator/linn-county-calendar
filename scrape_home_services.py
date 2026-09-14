#!/usr/bin/env python3
"""
Pulls home service businesses (plumbers, electricians, roofers, etc.) from
Google Maps via Outscraper (https://outscraper.com) -- a paid third-party
API that does the actual Google Maps scraping/anti-blocking work, so this
script is just "send a search, get structured results back." Requires
OUTSCRAPER_API_KEY in the environment.

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

NOTE ON FIELD NAMES: Outscraper's exact response shape isn't verified
against a live call here (no API key available while writing this) --
_get() tries several plausible key spellings per field, and unexpected
shapes are skipped with a warning rather than crashing the run, but the
first real run should be watched closely and this adjusted if fields come
back empty that shouldn't be.

Run:
    OUTSCRAPER_API_KEY=... python scrape_home_services.py
"""
import glob
import json
import os
import re
import sys
import time

import requests

from calendar_config import load_config, town_or_other

OUTSCRAPER_API_KEY = os.environ.get("OUTSCRAPER_API_KEY", "")
OUTSCRAPER_SEARCH_URL = "https://api.outscraper.com/maps/search-v3"
RESULTS_PER_QUERY = 40
POLL_ATTEMPTS = 10
POLL_INTERVAL_SECONDS = 6
REQUEST_DELAY_SECONDS = 2  # be polite between queries, not a rate-limit workaround

BUSINESS_DIR = "data/businesses"

# (directory category, what to search Google Maps for) -- category also
# becomes one of the checkboxes in docs/directory.html's filter, so keep
# these in sync with business_categories in docs/config.json.
HOME_SERVICE_QUERIES = [
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
    (permanently/temporarily closed, or missing what's actually
    required)."""
    status = (result.get("business_status") or "").upper()
    if status and status != "OPERATIONAL":
        return None

    name = (_get(result, "name") or "").strip()
    address = (_get(result, "full_address", "address", "formatted_address") or "").strip()
    if not name or not address:
        return None

    listing = {
        "name": name,
        "category": category,
        "town": town_or_other(address, config),
        "address": address,
        # Bookkeeping only -- build_business_directory.py whitelists which
        # fields reach the public docs/businesses.json, so these never
        # show up on the site itself. Kept so a stale/incorrect scraped
        # listing can be tracked back to its source, and so a future
        # "re-scrape and refresh" pass could match on place_id instead of
        # name+town.
        "source": "google_maps",
    }

    phone = (_get(result, "phone", "phone_number", "international_phone_number") or "").strip()
    if phone:
        listing["phone"] = phone

    website = (_get(result, "site", "website", "domain") or "").strip()
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


def main():
    if not OUTSCRAPER_API_KEY:
        print("ERROR: set OUTSCRAPER_API_KEY", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    existing_slugs = {
        os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob(os.path.join(BUSINESS_DIR, "*.json"))
    }

    added = 0
    for category, search_phrase in HOME_SERVICE_QUERIES:
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

            slug = f"{slugify(listing['town'])}-{slugify(listing['name'])}"
            if slug.strip("-") == "" or slug in existing_slugs:
                continue  # no usable name/town, or already have a file -- a hand-edited listing wins

            path = os.path.join(BUSINESS_DIR, f"{slug}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(listing, f, indent=2)
                f.write("\n")
            existing_slugs.add(slug)
            added += 1
            print(f"  + {listing['name']} ({listing['town']})")

        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"\nAdded {added} new listing(s).")


if __name__ == "__main__":
    main()
