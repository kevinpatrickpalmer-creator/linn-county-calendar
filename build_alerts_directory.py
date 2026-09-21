#!/usr/bin/env python3
"""
Builds docs/local-alerts.json from every approved alert in data/alerts/
(see data/alerts/README.md for how a file lands there). Same one-sided
build approach as build_notices_directory.py, kept as its own script
since this is a different content type (more urgent, much shorter
expiry) with its own board and directory.

Run:
    python build_alerts_directory.py
"""
import glob
import json
import os
import sys
from datetime import date, timedelta

from calendar_config import load_config

ALERT_DIR = "data/alerts"
OUTPUT_PATH = "docs/local-alerts.json"

# Written in this order for every alert, regardless of what order its
# own JSON keys were in -- keeps docs/local-alerts.json diffs stable
# from run to run.
FIELDS = ["category", "town", "message", "submitter_name", "photos", "posted"]
REQUIRED_FIELDS = ("category", "town", "message", "submitter_name")
LIST_FIELDS = {"photos"}


def load_alerts(config, today=None):
    """Same shape as load_notices() in build_notices_directory.py -- a
    malformed/incomplete/"Other"-town file is skipped or held back, and
    an old-enough alert expires by its "posted" date. Alerts don't stay
    up nearly as long as a Notice does (see alert_expiry_days in
    docs/config.json, the shortest window on the site) since the whole
    point is "current," a days-old alert about a road that's since
    reopened is actively misleading, not just stale."""
    today = today or date.today()
    expiry_days = config.get("alert_expiry_days", 5)
    alerts = []
    held_back = 0
    expired = 0
    for path in sorted(glob.glob(os.path.join(ALERT_DIR, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  WARNING: skipping unreadable alert {path}: {e}", file=sys.stderr)
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

        alert = {}
        for field in FIELDS:
            if field in LIST_FIELDS:
                raw_value = data.get(field)
                if isinstance(raw_value, list) and raw_value:
                    alert[field] = raw_value
                continue
            value = (data.get(field) or "").strip()
            if value:
                alert[field] = value
        if is_example:
            alert["example"] = True
        alerts.append(alert)

    # Newest first, same reasoning as every other expiring board.
    alerts.sort(key=lambda a: a.get("posted") or "", reverse=True)
    # Then pin any "example" alert(s) above everything else, newest-first
    # order preserved within each group since sort() is stable.
    alerts.sort(key=lambda a: not a.get("example", False))
    return alerts, held_back, expired


def main():
    config = load_config()
    alerts, held_back, expired = load_alerts(config)

    towns = sorted({a["town"] for a in alerts if a["town"] in config["towns"]})
    real_count = sum(1 for a in alerts if not a.get("example"))
    print(f"Building Local Alerts: {real_count} alert(s) across {len(towns)} of {len(config['towns'])} official towns")
    if held_back:
        print(f"  ({held_back} alert(s) held back -- town unresolved, still \"Other\" in data/alerts/)")
    if expired:
        print(f"  ({expired} alert(s) expired -- older than {config.get('alert_expiry_days', 5)} days, source file left in data/alerts/)")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(alerts, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
