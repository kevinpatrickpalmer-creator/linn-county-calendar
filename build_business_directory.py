#!/usr/bin/env python3
"""
Builds docs/businesses.json from every approved listing in
data/businesses/ (see data/businesses/README.md for how a file lands
there). Unlike scrape_linn_county_calendar.py, there's no scraping here
-- this just combines already-approved local JSON files into one file
docs/directory.html can fetch in a single request, instead of making it
walk the GitHub contents API itself (the way docs/manage-businesses.html
does, which is fine for an admin tool but would rate-limit fast against
public traffic).

Run:
    python build_business_directory.py
"""
import glob
import json
import os
import sys

from calendar_config import load_config

BUSINESS_DIR = "data/businesses"
OUTPUT_PATH = "docs/businesses.json"

# Written in this order for every listing that has a file, regardless of
# what order its own JSON keys were in -- keeps docs/businesses.json diffs
# stable from run to run. "place_id" and "source" are deliberately not
# here -- see data/businesses/README.md -- they're bookkeeping for the
# scraper's own dedup, never meant for the public site.
FIELDS = ["name", "category", "town", "address", "phone", "website", "email", "photo", "photos", "rating", "reviews", "hours", "description", "keywords"]
NUMERIC_FIELDS = {"rating", "reviews"}
# "keywords" is a list (Google's subtypes + reviews_tags -- see
# scrape_businesses.py's build_listing()), not a string like every other
# field here -- search-only, docs/directory.html never displays it.
# "photos" is also a list -- up to 3 repo-relative paths a person uploaded
# with their submission (see submit-business.html), distinct from "photo"
# (a single scraped Google image URL, see scrape_businesses.py). A listing
# can have either, neither, or in theory both.
LIST_FIELDS = {"keywords", "photos"}
# Fields that live per-branch on a multi-location listing's own
# "locations" entries instead of at the top level -- see
# _load_multi_location() below.
PER_LOCATION_FIELDS = {"town", "address", "phone"}


def _extract_fields(data, skip):
    """FIELDS not in SKIP, present and non-empty on DATA, as a dict --
    shared by both the single-town and multi-location loaders below so
    they stay in sync."""
    extracted = {}
    for field in FIELDS:
        if field in skip:
            continue
        raw_value = data.get(field)
        if field in NUMERIC_FIELDS:
            if isinstance(raw_value, (int, float)):
                extracted[field] = raw_value
            continue
        if field in LIST_FIELDS:
            if isinstance(raw_value, list) and raw_value:
                extracted[field] = raw_value
            continue
        value = (raw_value or "").strip()
        if value:
            extracted[field] = value
    return extracted


def _load_multi_location(path, data, name):
    """A listing with a "towns" array instead of a single "town" -- the
    same real business operating in more than one town (a chain like
    Casey's or Hunt Brothers Pizza, not just a coincidentally-shared
    name -- see data/businesses/README.md for how one of these gets
    created). Its own "locations" array carries the per-branch
    address/phone; whatever else the file has (category, rating, photo,
    website...) is treated as shared across every branch."""
    towns = [t.strip() for t in data["towns"] if isinstance(t, str) and t.strip() and t.strip() != "Other"]
    if not towns:
        print(f"  WARNING: skipping {path}, no usable towns", file=sys.stderr)
        return None

    listing = {"name": name, "towns": towns}
    listing.update(_extract_fields(data, skip={"name", "town", "address", "phone"}))

    locations = []
    for loc in data.get("locations") or []:
        if not isinstance(loc, dict):
            continue
        town = (loc.get("town") or "").strip()
        if not town:
            continue
        entry = {"town": town}
        for field in ("address", "phone"):
            value = (loc.get(field) or "").strip()
            if value:
                entry[field] = value
        locations.append(entry)
    if locations:
        listing["locations"] = locations

    return listing


def load_businesses():
    """A malformed or incomplete file is skipped with a warning rather
    than failing the whole build -- one bad listing shouldn't take down
    the rest of the directory. A listing whose town is literally "Other"
    is held back from the public site entirely rather than published with
    that unhelpful label, the file staying in data/businesses/ so it
    isn't lost. In practice this shouldn't fire often: scrape_businesses.py's
    fallback for a service-area business Google's own data doesn't tie to
    a specific town is "Linn County" (still true, unlike "Other"), and
    admin-business.html's "Other (not on this list)" option for a manual
    submission stores the actual place name typed in (e.g. "Hurricane
    Branch"), never the literal string "Other" -- this check is a
    backstop for old/stale data rather than the everyday mechanism."""
    businesses = []
    held_back = 0
    for path in sorted(glob.glob(os.path.join(BUSINESS_DIR, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  WARNING: skipping unreadable listing {path}: {e}", file=sys.stderr)
            continue

        name = (data.get("name") or "").strip()
        if not name:
            print(f"  WARNING: skipping {path}, missing required name", file=sys.stderr)
            continue

        if isinstance(data.get("towns"), list):
            listing = _load_multi_location(path, data, name)
            if listing:
                businesses.append(listing)
            continue

        town = (data.get("town") or "").strip()
        if not town:
            print(f"  WARNING: skipping {path}, missing required name/town", file=sys.stderr)
            continue
        if town == "Other":
            held_back += 1
            continue

        listing = {"name": name, "town": town}
        listing.update(_extract_fields(data, skip={"name", "town"}))
        businesses.append(listing)

    businesses.sort(key=lambda b: b["name"].lower())
    return businesses, held_back


def main():
    config = load_config()
    businesses, held_back = load_businesses()

    def towns_of(b):
        return b["towns"] if "towns" in b else [b["town"]]

    towns = sorted({t for b in businesses for t in towns_of(b) if t in config["towns"]})
    multi_location = sum(1 for b in businesses if "towns" in b)
    print(f"Building directory: {len(businesses)} listing(s) ({multi_location} multi-town) across {len(towns)} of {len(config['towns'])} official towns")
    if held_back:
        print(f"  ({held_back} listing(s) held back -- town unresolved, still \"Other\" in data/businesses/)")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(businesses, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
