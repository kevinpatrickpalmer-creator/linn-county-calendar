#!/usr/bin/env python3
"""
Builds docs/notices.json from every approved notice in data/notices/
(see data/notices/README.md for how a file lands there). Same
"combine approved local files into one fetchable JSON file" approach as
build_jobs_directory.py, kept as its own script since this is a
different content type (short-lived info, not a two-sided post) with
its own required fields and a shorter expiry window.

Run:
    python build_notices_directory.py
"""
import glob
import json
import os
import sys
from datetime import date, timedelta

from calendar_config import load_config

NOTICE_DIR = "data/notices"
OUTPUT_PATH = "docs/notices.json"

# Written in this order for every notice, regardless of what order its
# own JSON keys were in -- keeps docs/notices.json diffs stable from
# run to run.
FIELDS = ["town", "category", "message", "submitter_name", "photos", "posted"]
REQUIRED_FIELDS = ("town", "message", "submitter_name")
LIST_FIELDS = {"photos"}


def load_notices(config, today=None):
    """Same shape as load_posts() in build_jobs_directory.py -- a
    malformed/incomplete/"Other"-town file is skipped or held back, an
    old-enough notice expires by its "posted" date, and a pinned
    "example" notice is exempt from both and always sorts first."""
    today = today or date.today()
    expiry_days = config.get("notice_expiry_days", 14)
    notices = []
    held_back = 0
    expired = 0
    for path in sorted(glob.glob(os.path.join(NOTICE_DIR, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  WARNING: skipping unreadable notice {path}: {e}", file=sys.stderr)
            continue

        values = {field: (data.get(field) or "").strip() for field in REQUIRED_FIELDS}
        if not all(values.values()):
            print(f"  WARNING: skipping {path}, missing a required field ({REQUIRED_FIELDS})", file=sys.stderr)
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

        notice = {}
        for field in FIELDS:
            if field in LIST_FIELDS:
                raw_value = data.get(field)
                if isinstance(raw_value, list) and raw_value:
                    notice[field] = raw_value
                continue
            value = (data.get(field) or "").strip()
            if value:
                notice[field] = value
        if is_example:
            notice["example"] = True
        notices.append(notice)

    # Newest first, same reasoning as every other expiring board.
    notices.sort(key=lambda n: n.get("posted") or "", reverse=True)
    # Then pin any "example" notice(s) above everything else, newest-first
    # order preserved within each group since sort() is stable.
    notices.sort(key=lambda n: not n.get("example", False))
    return notices, held_back, expired


def main():
    config = load_config()
    notices, held_back, expired = load_notices(config)

    towns = sorted({n["town"] for n in notices if n["town"] in config["towns"]})
    real_count = sum(1 for n in notices if not n.get("example"))
    print(f"Building Community Notices: {real_count} notice(s) across {len(towns)} of {len(config['towns'])} official towns")
    if held_back:
        print(f"  ({held_back} notice(s) held back -- town unresolved, still \"Other\" in data/notices/)")
    if expired:
        print(f"  ({expired} notice(s) expired -- older than {config.get('notice_expiry_days', 14)} days, source file left in data/notices/)")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(notices, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
