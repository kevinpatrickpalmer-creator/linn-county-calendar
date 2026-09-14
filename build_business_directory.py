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
# stable from run to run.
FIELDS = ["name", "category", "town", "address", "phone", "website", "email", "hours", "description"]


def load_businesses():
    """A malformed or incomplete file is skipped with a warning rather
    than failing the whole build -- one bad listing shouldn't take down
    the rest of the directory."""
    businesses = []
    for path in sorted(glob.glob(os.path.join(BUSINESS_DIR, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  WARNING: skipping unreadable listing {path}: {e}", file=sys.stderr)
            continue

        name = (data.get("name") or "").strip()
        town = (data.get("town") or "").strip()
        if not name or not town:
            print(f"  WARNING: skipping {path}, missing required name/town", file=sys.stderr)
            continue

        listing = {"name": name, "town": town}
        for field in FIELDS:
            if field in ("name", "town"):
                continue
            value = (data.get(field) or "").strip()
            if value:
                listing[field] = value
        businesses.append(listing)

    businesses.sort(key=lambda b: b["name"].lower())
    return businesses


def main():
    config = load_config()
    businesses = load_businesses()

    towns = sorted({b["town"] for b in businesses if b["town"] in config["towns"]} | set())
    print(f"Building directory: {len(businesses)} listing(s) across {len(towns)} of {len(config['towns'])} towns")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(businesses, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
