#!/usr/bin/env python3
"""
Runs as part of the scheduled scrape workflow: compares the previously
published .ics against the freshly regenerated one, and emails the admin a
confirmation for any manually-submitted/approved event (UID starting with
"manual-") that's newly appeared since the last run.

Only manual events are considered -- scraped events change constantly and
would make this noisy; the point is to confirm "your approval just went
live," which only applies to the manual-submission pipeline.

Install:
    pip install icalendar requests

Run (in CI, old/new paths point at the pre- and post-scrape .ics):
    python notify_new_manual_events.py <old_ics_path> <new_ics_path>
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


def manual_events_by_uid(ics_path):
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
        if not uid.startswith("manual-"):
            continue
        events[uid] = {
            "name": str(component.get("summary", "")),
            "location": str(component.get("location", "")),
            "description": str(component.get("description", "")),
        }
    return events


def send_confirmation(event):
    lines = [f'"{event["name"]}" is now live on the {CONFIG["county_display_name"]} calendar.', ""]
    if event["location"]:
        lines.append(f"Location: {event['location']}")
    if event["description"]:
        lines.append(f"Description: {event['description']}")
    body = "\n".join(lines)

    resp = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
        json={
            "sender": {"email": SENDER_EMAIL, "name": SENDER_NAME},
            "to": [{"email": ADMIN_EMAIL}],
            "subject": f'Live: {event["name"]}',
            "textContent": body,
        },
        timeout=30,
    )
    resp.raise_for_status()


def main():
    if len(sys.argv) != 3:
        print("Usage: python notify_new_manual_events.py <old_ics_path> <new_ics_path>")
        sys.exit(1)

    old_path, new_path = sys.argv[1], sys.argv[2]

    if not BREVO_API_KEY:
        print("BREVO_API_KEY isn't set -- skipping new-event notifications.", file=sys.stderr)
        return

    old_events = manual_events_by_uid(old_path)
    new_events = manual_events_by_uid(new_path)

    newly_added = [uid for uid in new_events if uid not in old_events]
    if not newly_added:
        print("No newly-approved manual events since the last run.")
        return

    print(f"Found {len(newly_added)} newly-approved manual event(s), sending confirmations...")
    for uid in newly_added:
        event = new_events[uid]
        try:
            send_confirmation(event)
            print(f"  Sent confirmation for: {event['name']}")
        except requests.RequestException as e:
            print(f"  WARNING: failed to send confirmation for {event['name']}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
