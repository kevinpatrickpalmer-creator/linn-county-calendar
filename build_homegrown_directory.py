#!/usr/bin/env python3
"""
Builds docs/homegrown.json from every approved listing in
data/homegrown/ (see data/homegrown/README.md for how a file lands
there). Same "combine approved local files into one fetchable JSON file"
approach as build_business_directory.py, kept as its own script since
this is a different content type (people, not registered businesses)
with a different, simpler schema -- no scraping, no photo/rating, no
multi-location chains.

Run:
    python build_homegrown_directory.py
"""
import glob
import json
import os
import sys

from calendar_config import load_config

LISTING_DIR = "data/homegrown"
OUTPUT_PATH = "docs/homegrown.json"

# Written in this order for every listing that has a file, regardless of
# what order its own JSON keys were in -- keeps docs/homegrown.json diffs
# stable from run to run.
FIELDS = ["name", "category", "town", "phone", "email", "website", "availability", "description"]


def load_listings():
    """A malformed or incomplete file is skipped with a warning rather
    than failing the whole build. A listing whose town is literally
    "Other" is held back from the public site entirely rather than
    published with that unhelpful label -- see data/homegrown/README.md."""
    listings = []
    held_back = 0
    for path in sorted(glob.glob(os.path.join(LISTING_DIR, "*.json"))):
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
        if town == "Other":
            held_back += 1
            continue

        listing = {"name": name, "town": town}
        for field in FIELDS:
            if field in ("name", "town"):
                continue
            value = (data.get(field) or "").strip()
            if value:
                listing[field] = value
        listings.append(listing)

    listings.sort(key=lambda b: b["name"].lower())
    return listings, held_back


def main():
    config = load_config()
    listings, held_back = load_listings()

    towns = sorted({b["town"] for b in listings if b["town"] in config["towns"]})
    print(f"Building homegrown directory: {len(listings)} listing(s) across {len(towns)} of {len(config['towns'])} official towns")
    if held_back:
        print(f"  ({held_back} listing(s) held back -- town unresolved, still \"Other\" in data/homegrown/)")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(listings, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
