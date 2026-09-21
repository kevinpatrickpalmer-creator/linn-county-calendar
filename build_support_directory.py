#!/usr/bin/env python3
"""
Builds docs/support.json from every approved post in data/support/ (see
data/support/README.md for how a file lands there). Same two-sided
build approach as build_volunteer_directory.py, kept as its own script
since this is a different content type (a need, an organization's
standing resource, or a benefit/fundraiser to help meet one) with its
own board and directory -- and its own expiry rule, see load_posts()
below: only "needed" posts age off, an "offering" post is evergreen.

Run:
    python build_support_directory.py
"""
import glob
import json
import os
import sys
from datetime import date, timedelta

from calendar_config import load_config

POST_DIR = "data/support"
OUTPUT_PATH = "docs/support.json"

VALID_TYPES = {"needed", "offering"}

# Written in this order for every post, regardless of what order its own
# JSON keys were in -- keeps docs/support.json diffs stable from run to
# run.
FIELDS = ["type", "category", "name", "town", "description", "phone", "email", "photos", "posted"]
REQUIRED_FIELDS = ("type", "category", "name", "town", "description")
LIST_FIELDS = {"photos"}


def load_posts(config, today=None):
    """Same shape as load_posts() in build_volunteer_directory.py, with
    one difference: only "needed" posts expire by age. An "offering"
    post is an organization's standing resource (a food pantry, a
    clothing drive, a charity), evergreen the same way a Trading Post
    or Business Directory listing is, not a time-bound ask the way a
    personal request is -- it shouldn't age off the site on its own,
    only ever come down if the poster removes it with their code
    (Kevin's call, 2026-09-21: "anything evergreen should never expire
    unless taken down with a code"). A malformed, incomplete, or
    bad-type file is skipped with a warning; a post whose town is
    literally "Other" is held back; a pinned "example" post is exempt
    from expiry entirely and always sorts first."""
    today = today or date.today()
    expiry_days = config.get("support_expiry_days", 30)
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
        if not is_example and values["type"] == "needed" and posted:
            try:
                posted_date = date.fromisoformat(posted)
                if today - posted_date > timedelta(days=expiry_days):
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
        if is_example:
            post["example"] = True
        posts.append(post)

    # Newest first, same reasoning as every other expiring board.
    posts.sort(key=lambda p: p.get("posted") or "", reverse=True)
    # Then pin any "example" post(s) above everything else, newest-first
    # order preserved within each group since sort() is stable.
    posts.sort(key=lambda p: not p.get("example", False))
    return posts, held_back, expired


def main():
    config = load_config()
    posts, held_back, expired = load_posts(config)

    towns = sorted({p["town"] for p in posts if p["town"] in config["towns"]})
    real_posts = [p for p in posts if not p.get("example")]
    needed = sum(1 for p in real_posts if p["type"] == "needed")
    offering = len(real_posts) - needed
    print(f"Building Community Support: {len(real_posts)} post(s) ({needed} requests, {offering} offering help) across {len(towns)} of {len(config['towns'])} official towns")
    if held_back:
        print(f"  ({held_back} post(s) held back -- town unresolved, still \"Other\" in data/support/)")
    if expired:
        print(f"  ({expired} post(s) expired -- older than {config.get('support_expiry_days', 30)} days, source file left in data/support/)")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
