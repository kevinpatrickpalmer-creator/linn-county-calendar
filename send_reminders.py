#!/usr/bin/env python3
"""
Daily job: email a reminder to everyone who opted in, for every event
happening tomorrow.

Subscriber opt-ins (email + reminder + newsletter checkboxes) are collected
by docs/index.html, which posts directly to a Google Form; that form's
linked Google Sheet is published to the web as CSV, which this script reads
with a plain HTTP GET -- no Google API/auth needed. The newsletter opt-in
column is stored here but not otherwise used yet.

Sending uses Brevo's API, from an address at communitycalendarconnect.com
(domain-authenticated with SPF/DKIM/DMARC for proper deliverability).
Requires a BREVO_API_KEY environment variable/secret.

Install:
    pip install icalendar requests

Run:
    python send_reminders.py
"""
import csv
import io
import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from icalendar import Calendar

try:
    from zoneinfo import ZoneInfo
except ImportError:
    print("This script requires Python 3.9+ (for the zoneinfo module).")
    sys.exit(1)

ICS_PATH = "docs/linn_county_events.ics"
LOCAL_TZ = ZoneInfo("America/Chicago")

# Published-to-web CSV export of the Google Sheet linked to the sign-up
# form on docs/index.html (Google Sheets: File > Share > Publish to web).
# Publicly readable by design -- it's just email + two yes/no columns, no
# auth needed to fetch it, and it isn't linked from anywhere.
SUBSCRIBERS_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vST534r8ueuQPb5iovg38S_4nwqU5o5dTWsJ9Mrf1Kpiih-4Cz8TIyx6Tj_Q7dApMceQ-hDpgofMXu3/pub?output=csv"

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
SENDER_EMAIL = "linncounty@communitycalendarconnect.com"
SENDER_NAME = "Linn County Calendar"


def tomorrows_events():
    with open(ICS_PATH, "rb") as f:
        cal = Calendar.from_ical(f.read())

    today_local = datetime.now(LOCAL_TZ).date()
    tomorrow = today_local + timedelta(days=1)

    events = []
    for component in cal.walk("VEVENT"):
        dtstart = component.get("dtstart").dt

        if isinstance(dtstart, datetime):
            event_date = dtstart.astimezone(LOCAL_TZ).date()
            time_str = dtstart.astimezone(LOCAL_TZ).strftime("%-I:%M %p")
        else:
            # All-day event: dtstart is already a plain date, no timezone.
            event_date = dtstart
            time_str = "All day"

        if event_date != tomorrow:
            continue

        events.append(
            {
                "name": str(component.get("summary", "")),
                "time": time_str,
                "location": str(component.get("location", "")),
            }
        )

    return tomorrow, events


def load_reminder_subscribers():
    if SUBSCRIBERS_CSV_URL.startswith("YOUR_"):
        print("SUBSCRIBERS_CSV_URL isn't configured yet -- skipping reminder sends.", file=sys.stderr)
        return []

    resp = requests.get(SUBSCRIBERS_CSV_URL, timeout=30)
    resp.raise_for_status()

    reader = csv.DictReader(io.StringIO(resp.text))
    # Later rows override earlier ones for the same email, so resubmitting
    # the form (e.g. to unsubscribe by unchecking everything) always wins.
    latest_by_email = {}
    for row in reader:
        email = (row.get("Email") or "").strip().lower()
        if not email:
            continue
        latest_by_email[email] = row

    return [
        email
        for email, row in latest_by_email.items()
        if (row.get("Reminder") or "").strip().lower() == "yes"
    ]


def send_reminder_email(to_email, tomorrow, events):
    lines = [f"Events happening tomorrow ({tomorrow.strftime('%A, %B %-d')}):", ""]
    for ev in events:
        line = f"- {ev['name']} — {ev['time']}"
        if ev["location"]:
            line += f" @ {ev['location']}"
        lines.append(line)
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
            "subject": f"Reminder: {len(events)} Linn County event(s) tomorrow",
            "textContent": body,
        },
        timeout=30,
    )
    resp.raise_for_status()


def main():
    tomorrow, events = tomorrows_events()

    if not events:
        print(f"No events found for {tomorrow} -- nothing to send.")
        return

    print(f"Found {len(events)} event(s) for {tomorrow}.")

    if not BREVO_API_KEY:
        print("BREVO_API_KEY isn't set -- skipping reminder sends.", file=sys.stderr)
        return

    subscribers = load_reminder_subscribers()
    if not subscribers:
        print("No reminder subscribers -- nothing to send.")
        return

    print(f"Emailing {len(subscribers)} subscriber(s)...")
    sent, failed = 0, 0
    for email in subscribers:
        try:
            send_reminder_email(email, tomorrow, events)
            sent += 1
        except requests.RequestException as e:
            print(f"  WARNING: failed to email {email}: {e}", file=sys.stderr)
            failed += 1

    print(f"Done. Sent {sent}, failed {failed}.")


if __name__ == "__main__":
    main()
