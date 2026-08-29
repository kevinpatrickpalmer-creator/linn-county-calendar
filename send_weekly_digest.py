#!/usr/bin/env python3
"""
Weekly job: email a summary of the coming week's events to everyone who
opted in.

Reuses the exact same subscriber pipeline as send_reminders.py (see that
file's docstring for the full explanation): docs/index.html posts opt-ins
to a Google Form, whose linked Sheet is published to the web as CSV and
read here with a plain HTTP GET. This just reads a different column
("Weekly Digest" instead of "Reminder") from the same CSV.

For this to work, the Google Form needs a "Weekly Digest" yes/no question
(the CSV column name comes directly from the form question's title, so it
must be titled exactly that), and docs/config.json's
google_form.entry_weekly_digest needs that question's real entry ID
(same as entry_towns, still a placeholder as of this writing -- see
docs/index.html's submit handler for where entry IDs are used).

"This week" means the next 7 days starting today, not the calendar's
Monday-Sunday week -- avoids ambiguity about which day the digest runs on.

Install:
    pip install icalendar requests

Run:
    python send_weekly_digest.py
"""
import csv
import io
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import quote

import requests
from icalendar import Calendar

try:
    from zoneinfo import ZoneInfo
except ImportError:
    print("This script requires Python 3.9+ (for the zoneinfo module).")
    sys.exit(1)

from calendar_config import extract_town, load_config

CONFIG = load_config()

ICS_PATH = "docs/linn_county_events.ics"
LOCAL_TZ = ZoneInfo(CONFIG["timezone"])

SUBSCRIBERS_CSV_URL = CONFIG["subscribers_csv_url"]

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
SENDER_EMAIL = CONFIG["sender_email"]
SENDER_NAME = CONFIG["sender_name"]

# A subscriber with no towns picked gets every town's events -- for a full
# week across the whole county that can run long, so this keeps the email
# skimmable rather than listing all of them.
MAX_EVENTS_LISTED = 60


def week_ahead_events():
    with open(ICS_PATH, "rb") as f:
        cal = Calendar.from_ical(f.read())

    today_local = datetime.now(LOCAL_TZ).date()
    week_end = today_local + timedelta(days=6)

    events = []
    for component in cal.walk("VEVENT"):
        dtstart = component.get("dtstart").dt

        if isinstance(dtstart, datetime):
            event_date = dtstart.astimezone(LOCAL_TZ).date()
            time_str = dtstart.astimezone(LOCAL_TZ).strftime("%-I:%M %p")
        else:
            event_date = dtstart
            time_str = "All day"

        if not (today_local <= event_date <= week_end):
            continue

        location = str(component.get("location", ""))
        events.append(
            {
                "name": str(component.get("summary", "")),
                "date": event_date,
                "time": time_str,
                "location": location,
                "town": extract_town(location, CONFIG),
            }
        )

    events.sort(key=lambda ev: (ev["date"], ev["time"] == "All day", ev["time"]))
    return today_local, week_end, events


def load_digest_subscribers():
    """Returns a list of (email, towns) tuples for everyone who opted into
    the weekly digest. towns is a set of town names to filter to, or an
    empty set meaning "every town" (the default when nothing's checked)."""
    if SUBSCRIBERS_CSV_URL.startswith("YOUR_"):
        print("SUBSCRIBERS_CSV_URL isn't configured yet -- skipping weekly digest sends.", file=sys.stderr)
        return []

    resp = requests.get(SUBSCRIBERS_CSV_URL, timeout=30)
    resp.raise_for_status()

    reader = csv.DictReader(io.StringIO(resp.text))
    # Later rows override earlier ones for the same email, matching
    # send_reminders.py -- resubmitting the form always wins.
    latest_by_email = {}
    for row in reader:
        email = (row.get("Email") or "").strip().lower()
        if not email:
            continue
        latest_by_email[email] = row

    subscribers = []
    for email, row in latest_by_email.items():
        if (row.get("Weekly Digest") or "").strip().lower() != "yes":
            continue
        towns_raw = (row.get("Towns") or "").strip()
        towns = {t.strip() for t in towns_raw.split(",") if t.strip()}
        subscribers.append((email, towns))

    return subscribers


def send_digest_email(to_email, week_start, week_end, events):
    by_date = defaultdict(list)
    for ev in events:
        by_date[ev["date"]].append(ev)

    lines = [
        f"{len(events)} event(s) coming up in {CONFIG['county_display_name']} this week "
        f"({week_start.strftime('%A, %B %-d')} through {week_end.strftime('%A, %B %-d')}):",
        "",
    ]

    shown = 0
    for date in sorted(by_date):
        if shown >= MAX_EVENTS_LISTED:
            break
        lines.append(date.strftime("%A, %B %-d"))
        for ev in by_date[date]:
            if shown >= MAX_EVENTS_LISTED:
                break
            line = f"  - {ev['time']}: {ev['name']}"
            if ev["location"]:
                line += f" @ {ev['location']}"
            lines.append(line)
            shown += 1
        lines.append("")

    remaining = len(events) - shown
    if remaining > 0:
        lines.append(f"...and {remaining} more not shown here. See the full calendar online for everything.")
        lines.append("")

    unsubscribe_url = f"https://{CONFIG['domain']}/unsubscribe.html?email={quote(to_email)}"
    lines.append(f"Unsubscribe from these emails: {unsubscribe_url}")
    body = "\n".join(lines)

    resp = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key": BREVO_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "sender": {"email": SENDER_EMAIL, "name": SENDER_NAME},
            "to": [{"email": to_email}],
            "subject": f"This week's events in {CONFIG['county_display_name']} ({len(events)})",
            "textContent": body,
        },
        timeout=30,
    )
    resp.raise_for_status()


def main():
    week_start, week_end, events = week_ahead_events()

    if not events:
        print(f"No events found for {week_start} through {week_end} -- nothing to send.")
        return

    print(f"Found {len(events)} event(s) for {week_start} through {week_end}.")

    if not BREVO_API_KEY:
        print("BREVO_API_KEY isn't set -- skipping weekly digest sends.", file=sys.stderr)
        return

    subscribers = load_digest_subscribers()
    if not subscribers:
        print("No weekly digest subscribers -- nothing to send.")
        return

    print(f"Considering {len(subscribers)} weekly digest subscriber(s)...")
    sent, skipped, failed = 0, 0, 0
    for email, towns in subscribers:
        subscriber_events = (
            events if not towns else [ev for ev in events if ev["town"] in towns]
        )
        if not subscriber_events:
            skipped += 1
            continue
        try:
            send_digest_email(email, week_start, week_end, subscriber_events)
            sent += 1
        except requests.RequestException as e:
            print(f"  WARNING: failed to email {email}: {e}", file=sys.stderr)
            failed += 1

    print(f"Done. Sent {sent}, skipped (no matching town events) {skipped}, failed {failed}.")


if __name__ == "__main__":
    main()
