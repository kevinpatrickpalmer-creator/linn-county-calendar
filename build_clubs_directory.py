#!/usr/bin/env python3
"""
Builds docs/clubs.json from every approved post in data/clubs/ (see
data/clubs/README.md for how a file lands there). Same "combine approved
local files into one fetchable JSON file" approach as
build_jobs_directory.py, kept as its own script since this is a
different content type (two-sided club/class posts, not work, goods,
or lost pets) with its own required fields.

Run:
    python build_clubs_directory.py
"""
import glob
import json
import os
import sys
from datetime import date, timedelta

from calendar_config import load_config

POST_DIR = "data/clubs"
OUTPUT_PATH = "docs/clubs.json"

VALID_TYPES = {"looking", "offering"}

# Written in this order for every post, regardless of what order its own
# JSON keys were in -- keeps docs/clubs.json diffs stable from run to run.
FIELDS = ["type", "name", "ageGroup", "category", "town", "phone", "email", "description", "posted"]
REQUIRED_FIELDS = ("type", "name", "ageGroup", "town", "description")


def load_posts(config, today=None):
    """A malformed, incomplete, or bad-type file is skipped with a
    warning rather than failing the whole build. A post whose town is
    literally "Other" is held back from the public site entirely rather
    than published with that unhelpful label -- see data/clubs/README.md.

    A post older than config["club_expiry_days"] (by its "posted" date)
    is held back too, same reasoning as Jobs Bulletin. The source file
    in data/clubs/ is left alone either way -- this only controls what
    makes it into the published docs/clubs.json, so an expired post can
    still be found in git history rather than being destroyed. The
    pinned "example" post never expires."""
    today = today or date.today()
    expiry_days = config.get("club_expiry_days", 60)
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

        is_example = bool(data.get("example"))
        posted = (data.get("posted") or "").strip()
        if not is_example and posted:
            try:
                posted_date = date.fromisoformat(posted)
                if today - posted_date > timedelta(days=expiry_days):
                    expired += 1
                    continue
            except ValueError:
                pass

        post = {}
        for field in FIELDS:
            value = (data.get(field) or "").strip()
            if value:
                post[field] = value
        if is_example:
            post["example"] = True
        posts.append(post)

    # Newest first, so the page doesn't need to re-sort client-side --
    # a post missing "posted" sorts last rather than crashing the build.
    posts.sort(key=lambda p: p.get("posted") or "", reverse=True)
    # Then pin any "example" post(s) -- see data/clubs/README.md -- above
    # everything else, newest-first order preserved within each group
    # since sort() is stable.
    posts.sort(key=lambda p: not p.get("example", False))
    return posts, held_back, expired


def main():
    config = load_config()
    posts, held_back, expired = load_posts(config)

    towns = sorted({p["town"] for p in posts if p["town"] in config["towns"]})
    looking = sum(1 for p in posts if p["type"] == "looking")
    offering = len(posts) - looking
    print(f"Building Clubs & Classes: {len(posts)} post(s) ({looking} looking to join, {offering} offering) across {len(towns)} of {len(config['towns'])} official towns")
    if held_back:
        print(f"  ({held_back} post(s) held back -- town unresolved, still \"Other\" in data/clubs/)")
    if expired:
        print(f"  ({expired} post(s) expired -- older than {config.get('club_expiry_days', 60)} days, source file left in data/clubs/)")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
