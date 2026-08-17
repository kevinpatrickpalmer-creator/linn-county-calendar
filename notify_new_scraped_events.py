#!/usr/bin/env python3
"""
Runs once a day (.github/workflows/daily-new-events-digest.yml), separately
from the scraper's own every-4-hours schedule: compares today's published
.ics against the calendar as it was ~24 hours ago (pulled from git history)
and, if any *scraped* events are newly present since then, emails the admin
a single digest -- a lightweight daily "yes, the scrapers are still finding
new things" signal, not a play-by-play of every 4-hour run.

Manually-submitted/approved events (UID starting with "manual-") are
excluded here since notify_new_manual_events.py already sends a dedicated
confirmation for those (still on the every-4-hours schedule, since that one
is about confirming a specific approval went live promptly); including them
again in this digest would just be the same event announced twice.

Install:
    pip install icalendar requests

Run (old/new paths point at yesterday's and today's .ics):
    python notify_new_scraped_events.py <old_ics_path> <new_ics_path>
"""
import os
import sys

import requests
from icalendar import Calendar

from calendar_config import load_config

CONFIG = load_config()

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
SENDER_EMAIL = CONFIG["sender_email"]
SENDER_NAME = CONFIG["sender_name"]
ADMIN_EMAIL = CONFIG["admin_email"]

# Keep the digest skimmable even on a run that finds a big batch at once
# (e.g. a new sports season's whole schedule landing in one pass).
MAX_EVENTS_LISTED = 40


def scraped_events_by_uid(ics_path):
    if not os.path.exists(ics_path):
        return {}

    with open(ics_path, "rb") as f:
        try:
            cal = Calendar.from_ical(f.read())
        except ValueError:
            return {}

    events = {}
    for component in cal.walk("VEVENT"):
        uid = str(component.get("uid", ""))
        if not uid or uid.startswith("manual-"):
            continue

        dtstart = component.get("dtstart")
        date_str = ""
        if dtstart is not None:
            try:
                date_str = dtstart.dt.strftime("%Y-%m-%d")
            except (AttributeError, ValueError):
                date_str = ""

        events[uid] = {
            "name": str(component.get("summary", "")),
            "location": str(component.get("location", "")),
            "date": date_str,
        }
    return events


def send_digest(new_events):
    ordered = sorted(new_events.values(), key=lambda e: (e["date"], e["name"]))

    lines = [
        f"The scrapers found {len(ordered)} new event(s) on the "
        f"{CONFIG['county_display_name']} calendar this run.",
        "",
    ]
    for event in ordered[:MAX_EVENTS_LISTED]:
        when = event["date"] or "date unknown"
        where = f" -- {event['location']}" if event["location"] else ""
        lines.append(f"- {when}: {event['name']}{where}")

    remaining = len(ordered) - MAX_EVENTS_LISTED
    if remaining > 0:
        lines.append("")
        lines.append(f"...and {remaining} more not shown here.")

    body = "\n".join(lines)

    resp = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
        json={
            "sender": {"email": SENDER_EMAIL, "name": SENDER_NAME},
            "to": [{"email": ADMIN_EMAIL}],
            "subject": f"{len(ordered)} new event(s) found -- {CONFIG['county_display_name']} calendar",
            "textContent": body,
        },
        timeout=30,
    )
    resp.raise_for_status()


def main():
    if len(sys.argv) != 3:
        print("Usage: python notify_new_scraped_events.py <old_ics_path> <new_ics_path>")
        sys.exit(1)

    old_path, new_path = sys.argv[1], sys.argv[2]

    if not BREVO_API_KEY:
        print("BREVO_API_KEY isn't set -- skipping new-scraped-event digest.", file=sys.stderr)
        return

    old_events = scraped_events_by_uid(old_path)
    new_events = scraped_events_by_uid(new_path)

    newly_added = {uid: ev for uid, ev in new_events.items() if uid not in old_events}
    if not newly_added:
        print("No newly-scraped events since the last run.")
        return

    print(f"Found {len(newly_added)} newly-scraped event(s), sending digest...")
    try:
        send_digest(newly_added)
        print("  Sent digest email.")
    except requests.RequestException as e:
        print(f"  WARNING: failed to send new-events digest: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
