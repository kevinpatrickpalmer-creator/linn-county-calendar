#!/usr/bin/env python3
"""
Builds docs/lost-found.json from every approved post in data/lost-found/
(see data/lost-found/README.md for how a file lands there). Same
"combine approved local files into one fetchable JSON file" approach as
build_jobs_directory.py, kept as its own script since this is a
different content type (lost/found pets and items, not work) with its
own required fields and an optional photo.

Run:
    python build_lost_found_directory.py
"""
import glob
import json
import os
import sys

from calendar_config import load_config

POST_DIR = "data/lost-found"
OUTPUT_PATH = "docs/lost-found.json"

VALID_TYPES = {"lost", "found"}

# Written in this order for every post, regardless of what order its own
# JSON keys were in -- keeps docs/lost-found.json diffs stable from run
# to run.
FIELDS = ["type", "category", "name", "town", "date", "description", "contact_name", "phone", "email", "photo", "posted"]
REQUIRED_FIELDS = ("type", "category", "name", "town", "date", "description")


def load_posts():
    """A malformed, incomplete, or bad-type file is skipped with a
    warning rather than failing the whole build. A post whose town is
    literally "Other" is held back from the public site entirely rather
    than published with that unhelpful label -- see
    data/businesses/README.md for why."""
    posts = []
    held_back = 0
    for path in sorted(glob.glob(os.path.join(POST_DIR, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  WARNING: skipping unreadable post {path}: {e}", file=sys.stderr)
            continue

        values = {field: (data.get(field) or "").strip() for field in REQUIRED_FIELDS}
        if not all(values.values()):
            print(f"  WARNING: skipping {path}, missing a required field ({REQUIRED_FIELDS})", file=sys.stderr)
            continue
        if values["type"] not in VALID_TYPES:
            print(f"  WARNING: skipping {path}, type must be one of {sorted(VALID_TYPES)}", file=sys.stderr)
            continue
        if values["town"] == "Other":
            held_back += 1
            continue

        post = {}
        for field in FIELDS:
            value = (data.get(field) or "").strip()
            if value:
                post[field] = value
        posts.append(post)

    # Newest first, so the page doesn't need to re-sort client-side --
    # a post missing "posted" (shouldn't happen via admin-lost-found.html,
    # but cheap to guard) sorts last rather than crashing the build.
    posts.sort(key=lambda p: p.get("posted") or "", reverse=True)
    return posts, held_back


def main():
    config = load_config()
    posts, held_back = load_posts()

    towns = sorted({p["town"] for p in posts if p["town"] in config["towns"]})
    lost = sum(1 for p in posts if p["type"] == "lost")
    found = len(posts) - lost
    print(f"Building Lost & Found: {len(posts)} post(s) ({lost} lost, {found} found) across {len(towns)} of {len(config['towns'])} official towns")
    if held_back:
        print(f"  ({held_back} post(s) held back -- town unresolved, still \"Other\" in data/lost-found/)")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
