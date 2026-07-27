#!/usr/bin/env python3
"""
Scrape community events from the Linn County Leader calendar and write them
out as a subscribable .ics calendar file.

IMPORTANT: linncountyleader.com/calendar/ does NOT contain event data in its
raw HTML. Events are rendered entirely client-side by a third-party widget
(CitySpark) after the page loads -- a plain `requests.get()` returns a
WordPress shell page with no events in it at all. So this script uses
Playwright to load the page in a real (headless) browser, waits for the
widget to render, and only then hands the resulting HTML to BeautifulSoup
for the actual parsing/extraction.

The calendar widget defaults to showing events within 25 miles of
Marceline/Brookfield, MO -- that's the site's own default view, so this
script's output should match what you see when you visit the page yourself.

Install:
    pip install playwright beautifulsoup4 icalendar
    playwright install chromium

Run:
    python scrape_linn_county_calendar.py
"""
import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    print("This script requires Python 3.9+ (for the zoneinfo module).")
    sys.exit(1)

try:
    from icalendar import Calendar, Event
except ImportError:
    print(
        "The `icalendar` package isn't installed.\n"
        "Install with:\n"
        "    pip install icalendar"
    )
    sys.exit(1)

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print(
        "Playwright isn't installed. This page loads its events via "
        "JavaScript, so plain requests+BeautifulSoup can't scrape it -- "
        "you need a real browser to render it first.\n\n"
        "Install with:\n"
        "    pip install playwright beautifulsoup4\n"
        "    playwright install chromium"
    )
    sys.exit(1)

CALENDAR_URL = "https://www.linncountyleader.com/calendar/"
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s?[ap]m\b", re.IGNORECASE)
EVENT_ID_RE = re.compile(r"#/details/[^/]+/(\d+)/")
LOCAL_TZ = ZoneInfo("America/Chicago")  # Linn County, MO
# Written into docs/ so GitHub Pages (serving from /docs) can host it directly.
ICS_PATH = "docs/linn_county_events.ics"
DEFAULT_DURATION = timedelta(hours=1)
# One JSON file per community-submitted event that's been approved (see
# docs/admin.html). Rejected/pending submissions never get a file here, so
# they structurally can't reach the .ics -- there's no "is it approved?"
# check to get wrong.
MANUAL_EVENTS_DIR = "data/manual_events"


def get_list_html(page):
    page.goto(CALENDAR_URL, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector(".csEvWrap", timeout=20000)
    except Exception:
        # Leave evidence behind so a failure in CI (no display to look at)
        # can still be diagnosed after the fact.
        page.screenshot(path="debug_screenshot.png", full_page=True)
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        raise

    # The widget lazy-renders more tiles as you scroll; keep scrolling until
    # the tile count stops growing.
    prev_count = -1
    for _ in range(6):
        count = page.eval_on_selector_all(".csEvWrap", "els => els.length")
        if count == prev_count:
            break
        prev_count = count
        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(800)

    return page.content()


def parse_events(html):
    soup = BeautifulSoup(html, "html.parser")
    events = []

    for tile in soup.select(".csEvWrap"):
        name_el = tile.select_one(".csOneLine span")
        name = name_el.get_text(strip=True) if name_el else ""

        venue_el = tile.select_one(".cityVenue")
        location = venue_el.get_text(" ", strip=True) if venue_el else ""
        location = re.sub(r"\s*\|\s*", " | ", location)

        date = (tile.get("data-date") or "")[:10]  # YYYY-MM-DD

        time_match = TIME_RE.search(tile.get_text(" ", strip=True))
        event_time = time_match.group(0) if time_match else ""

        link_el = tile.select_one("a")
        href = link_el["href"] if link_el and link_el.has_attr("href") else ""

        id_match = EVENT_ID_RE.search(href)
        event_id = id_match.group(1) if id_match else ""

        events.append(
            {
                "name": name,
                "date": date,
                "time": event_time,
                "location": location,
                "description": "",  # filled in below from the detail view
                "href": href,
                "event_id": event_id,
                "start_iso": None,  # filled in below from the detail view
                "end_iso": None,
            }
        )

    return events


def load_manual_events():
    """Load community-submitted events that have been approved (see
    docs/admin.html for how a file lands here). Each file becomes one event,
    in the same shape parse_events() produces, so build_calendar() and
    event_uid() need no special-casing for them. A malformed file is skipped
    with a warning rather than failing the whole run -- one bad manual entry
    shouldn't take down the scraped events too."""
    manual_events = []
    for path in sorted(glob.glob(os.path.join(MANUAL_EVENTS_DIR, "*.json"))):
        slug = os.path.splitext(os.path.basename(path))[0]
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  WARNING: skipping unreadable manual event {path}: {e}", file=sys.stderr)
            continue

        name = (data.get("name") or "").strip()
        date = (data.get("date") or "").strip()
        if not name or not date:
            print(f"  WARNING: skipping {path}, missing required name/date", file=sys.stderr)
            continue

        manual_events.append(
            {
                "name": name,
                "date": date,
                "time": (data.get("time") or "").strip(),
                "location": (data.get("location") or "").strip(),
                "description": (data.get("description") or "").strip(),
                "href": "",  # no CitySpark detail page to fetch
                "event_id": f"manual-{slug}",
                "start_iso": None,
                "end_iso": None,
            }
        )

    return manual_events


def fill_descriptions(page, events):
    """Each event's detail view embeds a schema.org JSON-LD block with a
    "description" field. It's blank for most events on this site, but we
    pull it whenever it's populated."""
    for i, ev in enumerate(events, 1):
        if not ev["href"]:
            continue
        print(f"  checking event {i}/{len(events)}...", end="\r", file=sys.stderr)
        page.evaluate("h => { location.hash = h; }", ev["href"])
        try:
            # state="attached": a <script> tag is never "visible", which is
            # wait_for_selector's default state, so that would always time out.
            page.wait_for_selector(
                ".csRoutingDetails script[type='application/ld+json']",
                state="attached",
                timeout=3000,
            )
        except Exception:
            continue

        detail_soup = BeautifulSoup(page.content(), "html.parser")
        script = detail_soup.select_one(
            ".csRoutingDetails script[type='application/ld+json']"
        )
        if not script or not script.string:
            continue
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            continue

        # The description field can itself contain HTML (e.g. "<p>...</p>");
        # strip it down to plain text.
        raw_description = data.get("description") or ""
        ev["description"] = BeautifulSoup(raw_description, "html.parser").get_text(" ", strip=True)
        ev["start_iso"] = data.get("startDate")
        ev["end_iso"] = data.get("endDate")

    print(" " * 40, end="\r", file=sys.stderr)


def _parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def event_uid(ev):
    """A stable, deterministic UID per (event, occurrence date, time) so
    re-running the scraper updates existing calendar entries instead of
    duplicating them. The date alone isn't always enough -- a handful of
    events on this site (e.g. "MHS Homecoming") list the same underlying
    event twice on one day at two different times -- so the time is folded
    in too. Falls back to a slug of the name if CitySpark's event id is
    missing for some reason."""
    key = ev["event_id"] or re.sub(r"\W+", "-", ev["name"].lower()).strip("-")
    time_slug = re.sub(r"\D", "", ev["time"]) if ev["time"] else "allday"
    return f"{key}-{ev['date']}-{time_slug}@linn-county-scraper.local"


def build_calendar(events):
    cal = Calendar()
    cal.add("prodid", "-//Linn County Leader Events Scraper//linn-county-scraper.local//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", "Linn County Leader Community Events")
    cal.add("x-wr-timezone", "America/Chicago")
    cal.add("x-published-ttl", "PT4H")  # matches the GitHub Actions refresh cadence

    now_utc = datetime.now(timezone.utc)

    for ev in events:
        if not ev["name"] or not ev["date"]:
            continue

        event = Event()
        event.add("uid", event_uid(ev))
        event.add("summary", ev["name"])
        event.add("dtstamp", now_utc)

        start_date = datetime.strptime(ev["date"], "%Y-%m-%d").date()

        if ev["time"]:
            # A timed event: parse "6:30 pm" against its calendar date in the
            # site's local timezone.
            dtstart = datetime.strptime(
                f"{ev['date']} {ev['time'].upper()}", "%Y-%m-%d %I:%M %p"
            ).replace(tzinfo=LOCAL_TZ)

            duration = DEFAULT_DURATION
            start_iso = _parse_iso(ev.get("start_iso"))
            end_iso = _parse_iso(ev.get("end_iso"))
            if start_iso and end_iso and end_iso > start_iso:
                duration = end_iso - start_iso

            dtend = dtstart + duration
            # Convert to UTC so the file needs no embedded VTIMEZONE block
            # (a bare TZID like "America/Chicago" isn't RFC 5545-complete
            # without one, and some calendar apps are strict about it).
            event.add("dtstart", dtstart.astimezone(timezone.utc))
            event.add("dtend", dtend.astimezone(timezone.utc))
        else:
            # No time listed on the page -> treat as an all-day event.
            # DTEND for all-day events is exclusive, so it's the next day.
            event.add("dtstart", start_date)
            event.add("dtend", start_date + timedelta(days=1))

        if ev["location"]:
            event.add("location", ev["location"])
        if ev["description"]:
            event.add("description", ev["description"])

        cal.add_component(event)

    return cal


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        html = get_list_html(page)
        events = parse_events(html)
        fill_descriptions(page, events)

        browser.close()

    manual_events = load_manual_events()
    if manual_events:
        print(f"Including {len(manual_events)} approved community-submitted event(s)\n")
        events.extend(manual_events)

    if not events:
        print("No events found -- the page structure may have changed.")
        sys.exit(1)

    print(f"Found {len(events)} events on {CALENDAR_URL}\n")
    for ev in events:
        when = ev["date"]
        if ev["time"]:
            when += f"  {ev['time']}"
        print(when)
        print(f"  {ev['name']}")
        if ev["location"]:
            print(f"  @ {ev['location']}")
        if ev["description"]:
            print(f"  {ev['description']}")
        print()

    calendar = build_calendar(events)
    ics_bytes = calendar.to_ical()
    os.makedirs(os.path.dirname(ICS_PATH) or ".", exist_ok=True)
    with open(ICS_PATH, "wb") as f:
        f.write(ics_bytes)

    print(f"Wrote {ICS_PATH}\n")
    print(f"----- {ICS_PATH} contents -----")
    print(ics_bytes.decode("utf-8"))


if __name__ == "__main__":
    main()
