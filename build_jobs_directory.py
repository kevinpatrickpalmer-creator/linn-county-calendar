#!/usr/bin/env python3
"""
Builds docs/jobs.json from every approved post in data/jobs/ (see
data/jobs/README.md for how a file lands there). Same "combine approved
local files into one fetchable JSON file" approach as
build_trading_post_directory.py, kept as its own script since this is a
different content type (two-sided help-wanted/help-offered posts, not
goods or businesses) with its own required fields.

Run:
    python build_jobs_directory.py
"""
import glob
import json
import os
import sys

from calendar_config import load_config

POST_DIR = "data/jobs"
OUTPUT_PATH = "docs/jobs.json"

VALID_TYPES = {"needed", "offering"}

# Written in this order for every post, regardless of what order its own
# JSON keys were in -- keeps docs/jobs.json diffs stable from run to run.
FIELDS = ["type", "name", "category", "town", "phone", "email", "description", "posted"]
REQUIRED_FIELDS = ("type", "name", "town", "description")


def load_posts():
    """A malformed, incomplete, or bad-type file is skipped with a
    warning rather than failing the whole build. A post whose town is
    literally "Other" is held back from the public site entirely rather
    than published with that unhelpful label -- see data/jobs/README.md."""
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
        if data.get("example"):
            post["example"] = True
        posts.append(post)

    # Newest first, so the page doesn't need to re-sort client-side --
    # a post missing "posted" (shouldn't happen via admin-job.html, but
    # cheap to guard) sorts last rather than crashing the build.
    posts.sort(key=lambda p: p.get("posted") or "", reverse=True)
    # Then pin any "example" post(s) -- see data/jobs/README.md -- above
    # everything else, newest-first order preserved within each group
    # since sort() is stable.
    posts.sort(key=lambda p: not p.get("example", False))
    return posts, held_back


def main():
    config = load_config()
    posts, held_back = load_posts()

    towns = sorted({p["town"] for p in posts if p["town"] in config["towns"]})
    needed = sum(1 for p in posts if p["type"] == "needed")
    offering = len(posts) - needed
    print(f"Building jobs bulletin: {len(posts)} post(s) ({needed} needing help, {offering} offering help) across {len(towns)} of {len(config['towns'])} official towns")
    if held_back:
        print(f"  ({held_back} post(s) held back -- town unresolved, still \"Other\" in data/jobs/)")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
