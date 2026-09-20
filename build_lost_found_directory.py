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
from datetime import date, timedelta

from calendar_config import load_config

POST_DIR = "data/lost-found"
OUTPUT_PATH = "docs/lost-found.json"

VALID_TYPES = {"lost", "found"}

# Written in this order for every post, regardless of what order its own
# JSON keys were in -- keeps docs/lost-found.json diffs stable from run
# to run.
FIELDS = ["type", "category", "name", "town", "date", "description", "contact_name", "phone", "email", "photos", "posted"]
REQUIRED_FIELDS = ("type", "category", "name", "town", "date", "description")
# "photos" is a list (up to 3 repo-relative paths, see
# submit-lost-found.html), not a string like every other field here.
LIST_FIELDS = {"photos"}


def load_posts(config, today=None):
    """A malformed, incomplete, or bad-type file is skipped with a
    warning rather than failing the whole build. A post whose town is
    literally "Other" is held back from the public site entirely rather
    than published with that unhelpful label -- see
    data/businesses/README.md for why.

    A post older than its category's window in
    config["lost_found_expiry_days"] (by its "posted" date) is held
    back too -- pets get longer than items since they turn up on their
    own timeline, not a browsing reader's. "Other" uses the item
    window. The source file in data/lost-found/ is left alone either
    way -- this only controls what makes it into the published
    docs/lost-found.json, so an expired post can still be found in git
    history rather than being destroyed."""
    today = today or date.today()
    expiry_days = config.get("lost_found_expiry_days", {"pet": 60, "item": 30})
    posts = []
    held_back = 0
    expired = 0
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

        category_window = expiry_days["pet"] if values["category"] == "Pet" else expiry_days["item"]
        posted = (data.get("posted") or "").strip()
        if posted:
            try:
                posted_date = date.fromisoformat(posted)
                if today - posted_date > timedelta(days=category_window):
                    expired += 1
                    continue
            except ValueError:
                pass

        post = {}
        for field in FIELDS:
            if field in LIST_FIELDS:
                raw_value = data.get(field)
                if isinstance(raw_value, list) and raw_value:
                    post[field] = raw_value
                continue
            value = (data.get(field) or "").strip()
            if value:
                post[field] = value
        posts.append(post)

    # Newest first, so the page doesn't need to re-sort client-side --
    # a post missing "posted" (shouldn't happen via admin-lost-found.html,
    # but cheap to guard) sorts last rather than crashing the build.
    posts.sort(key=lambda p: p.get("posted") or "", reverse=True)
    return posts, held_back, expired


def main():
    config = load_config()
    posts, held_back, expired = load_posts(config)

    towns = sorted({p["town"] for p in posts if p["town"] in config["towns"]})
    lost = sum(1 for p in posts if p["type"] == "lost")
    found = len(posts) - lost
    print(f"Building Lost & Found: {len(posts)} post(s) ({lost} lost, {found} found) across {len(towns)} of {len(config['towns'])} official towns")
    if held_back:
        print(f"  ({held_back} post(s) held back -- town unresolved, still \"Other\" in data/lost-found/)")
    if expired:
        expiry = config.get("lost_found_expiry_days", {"pet": 60, "item": 30})
        print(f"  ({expired} post(s) expired -- older than {expiry['pet']} days for pets / {expiry['item']} days for items, source file left in data/lost-found/)")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
