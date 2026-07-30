#!/usr/bin/env python3
"""
Scrape community events from multiple Linn County sources and write them
out as one combined, subscribable .ics calendar file.

Source 1 -- Linn County Leader's CitySpark widget:
linncountyleader.com/calendar/ does NOT contain event data in its raw
HTML. Events are rendered entirely client-side by a third-party widget
(CitySpark) after the page loads -- a plain `requests.get()` returns a
WordPress shell page with no events in it at all. So this script uses
Playwright to load the page in a real (headless) browser, waits for the
widget to render, and only then hands the resulting HTML to BeautifulSoup
for the actual parsing/extraction. The widget defaults to showing events
within 25 miles of Marceline/Brookfield, MO -- that's the site's own
default view, so this script's output should match what you see when you
visit the page yourself.

Source 2 -- the City of Brookfield's own calendar:
CitySpark's coverage turned out to be almost entirely Marceline-based
institutions (the newspaper that runs it is Marceline-based, and only
onboarded contacts it already had a relationship with). Brookfield --
the county's largest town -- has real, actively-maintained event data of
its own, just on a completely separate site. Unlike CitySpark, this one
needs no headless browser: see get_brookfield_city_events() for details.

Source 3 -- Brookfield R-III School District's game schedule:
Doesn't live on the district's own site at all -- it's embedded there
from MSHSAA (Missouri State High School Activities Association), which
hosts a shared calendar for every Missouri high school by school ID. See
get_brookfield_schools_events() for details; notably, that function
would work for any other Missouri school just by changing the ID.

Each source's output gets normalized to the same event dict shape before
merging, so adding another town's source later just means writing one
more `get_*_events()` function and extending it into `events` in main() --
build_calendar(), event_uid(), etc. need no changes per source.

Everything that differs between deployments (timezone, calendar display
name, UID namespace) lives in docs/config.json, loaded via
calendar_config.py. The source URLs and scraping/parsing logic below are
specific to these particular sites and aren't config-driven -- a new
town/county needs its own source scrapers unless its sources happen to
run the same platforms (CitySpark, "Events Calendar WD", etc.).

Install:
    pip install playwright beautifulsoup4 icalendar requests
    playwright install chromium

Run:
    python scrape_linn_county_calendar.py
"""
import glob
import json
import os
import re
import sys
import time
import warnings
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

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

from calendar_config import load_config

CONFIG = load_config()

# This scraper is specific to linncountyleader.com's CitySpark widget --
# a new instance for a different town/county needs its own scraper (or
# none at all, relying purely on manual submissions) unless that source
# happens to also run on CitySpark. Not something config.json can abstract
# away, so it stays a plain constant here rather than moving to config.
CALENDAR_URL = "https://www.linncountyleader.com/calendar/"

# Second source: the City of Brookfield runs its own event calendar (a
# WordPress "Events Calendar WD" site) that's completely disconnected from
# CitySpark -- Brookfield is the county's largest town but had zero
# presence in the CitySpark widget above, because that widget only shows
# whatever the Marceline-based newspaper happened to onboard. Unlike
# CitySpark, this one needs no headless browser: each event is its own
# plain HTML page with a schema.org Event JSON-LD block, and the site's
# own XML sitemap lists every event permalink directly, so there's no
# month-by-month pagination to reverse-engineer either.
BROOKFIELD_CITY_BASE = "https://brookfieldcity.com"
BROOKFIELD_REQUEST_HEADERS = {"User-Agent": "linn-county-calendar-bot/1.0"}

# Third source: Brookfield R-III School District's actual game schedule
# doesn't live on the district's own (Wix) site at all -- it's embedded
# there via an iframe pointing at MSHSAA (Missouri State High School
# Activities Association), which hosts a shared calendar for every
# Missouri high school by school ID. Plain server-rendered legacy
# ASP.NET HTML, no headless browser needed. Because MSHSAA hosts this
# identically for every MO school, get_brookfield_schools_events() below
# would work for any other Missouri school just by changing the ID.
MSHSAA_SCHOOL_ID = "244"  # Brookfield R-III

TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s?[ap]m\b", re.IGNORECASE)
EVENT_ID_RE = re.compile(r"#/details/[^/]+/(\d+)/")
LOCAL_TZ = ZoneInfo(CONFIG["timezone"])
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


def _parse_brookfield_datetime(value):
    """Brookfield's event pages give dates as "2026/09/01 8:00am" (no space
    before am/pm) rather than ISO 8601, so this needs its own parser."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y/%m/%d %I:%M%p").replace(tzinfo=LOCAL_TZ)
    except ValueError:
        return None


def get_brookfield_city_events():
    """Fetch every event from the City of Brookfield's own calendar via its
    XML sitemap (only ~100 events total since 2020, small enough to fetch
    in full), filtering down to upcoming ones. Each event page embeds a
    schema.org Event JSON-LD block with everything needed, so no separate
    HTML-parsing logic is required the way CitySpark's tiles need."""
    try:
        resp = requests.get(
            f"{BROOKFIELD_CITY_BASE}/ecwd_event-sitemap.xml",
            headers=BROOKFIELD_REQUEST_HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  WARNING: couldn't fetch Brookfield's event sitemap: {e}", file=sys.stderr)
        return []

    sitemap_soup = BeautifulSoup(resp.content, "html.parser")
    event_urls = [
        loc.get_text(strip=True)
        for loc in sitemap_soup.find_all("loc")
        if loc.get_text(strip=True).rstrip("/") != f"{BROOKFIELD_CITY_BASE}/event"
    ]

    today = datetime.now(LOCAL_TZ).date()
    events = []
    for i, url in enumerate(event_urls, 1):
        print(f"  checking Brookfield event {i}/{len(event_urls)}...", end="\r", file=sys.stderr)
        try:
            page = requests.get(url, headers=BROOKFIELD_REQUEST_HEADERS, timeout=30)
            page.raise_for_status()
        except requests.RequestException:
            continue
        finally:
            time.sleep(0.2)  # be polite to a small town's server

        detail_soup = BeautifulSoup(page.content, "html.parser")
        data = None
        for script in detail_soup.select('script[type="application/ld+json"]'):
            try:
                candidate = json.loads(script.string or "")
            except json.JSONDecodeError:
                continue
            if candidate.get("@type") == "Event":
                data = candidate
                break
        if not data:
            continue

        start = _parse_brookfield_datetime(data.get("startDate"))
        if not start or start.date() < today:
            continue  # skip anything unparseable or already in the past
        end = _parse_brookfield_datetime(data.get("endDate"))

        venue = ((data.get("location") or {}).get("name") or "").strip()
        location = f"{venue} | Brookfield, {CONFIG['state']}" if venue else f"Brookfield, {CONFIG['state']}"

        slug = url.rstrip("/").rsplit("/", 1)[-1]

        events.append(
            {
                "name": (data.get("name") or "").strip(),
                "date": start.strftime("%Y-%m-%d"),
                "time": start.strftime("%I:%M %p"),
                "location": location,
                "description": (data.get("description") or "").strip(),
                "href": "",
                "event_id": f"bfcity-{slug}",
                "start_iso": start.isoformat(),
                "end_iso": end.isoformat() if end else None,
            }
        )

    print(" " * 40, end="\r", file=sys.stderr)
    return events


def get_brookfield_schools_events():
    """Fetch Brookfield R-III's game schedule from MSHSAA's shared
    calendar (see MSHSAA_SCHOOL_ID above for why this lives there rather
    than on the district's own site). The page is one big legacy ASP.NET
    grid: a `tr.fs_columnheader` row holds a date, followed by zero or
    more `tr.withBorderBottom` rows (one per matchup) until the next date
    header. A row already in the past carries a `past` class -- skipped
    here in favor of a real date comparison, since relying on the site's
    own "is this past" judgement would silently misbehave if its notion
    of "today" ever drifted from ours."""
    url = f"https://www.mshsaa.org/Shared/CalendarList.aspx?s={MSHSAA_SCHOOL_ID}&noheader=1"
    try:
        resp = requests.get(url, headers=BROOKFIELD_REQUEST_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  WARNING: couldn't fetch Brookfield's MSHSAA schedule: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    grid = soup.find("table", class_="fs_grid")
    if not grid:
        print("  WARNING: MSHSAA schedule page structure has changed (no fs_grid table found)", file=sys.stderr)
        return []

    today = datetime.now(LOCAL_TZ).date()
    current_date = None
    events = []

    for row in grid.find_all("tr", recursive=True):
        classes = row.get("class") or []

        if "fs_columnheader" in classes:
            # e.g. "Saturday, August 22, 2026 Sat, Aug 22, 2026" -- the
            # long form always comes first.
            header_match = re.match(
                r"[A-Za-z]+, ([A-Za-z]+ \d{1,2}, \d{4})", row.get_text(" ", strip=True)
            )
            current_date = None
            if header_match:
                try:
                    current_date = datetime.strptime(header_match.group(1), "%B %d, %Y").date()
                except ValueError:
                    current_date = None
            continue

        if "withBorderBottom" not in classes or "past" in classes:
            continue
        if current_date is None or current_date < today:
            continue

        tds = row.find_all("td", recursive=False)
        if len(tds) < 4:
            continue

        opponent_cell = tds[1]
        # The opponent/event name is the cell's own direct text, before
        # its nested sport/level <div>s and mobile-only duplicate info.
        opponent = " ".join(
            t.strip() for t in opponent_cell.find_all(string=True, recursive=False) if t.strip()
        )
        if not opponent or "dead period" in opponent.lower():
            continue  # "Sport/Activity Dead Period" rows aren't real events

        sport_el = opponent_cell.select_one("div.darkgray")
        sport = sport_el.get_text(" ", strip=True) if sport_el else ""
        sport_short = sport.split(":")[0].strip()

        home_away_el = tds[2].select_one("span.small")
        home_away = home_away_el.get_text(strip=True) if home_away_el else ""

        # A single matchup can list several times, one per level (e.g. JV
        # at 5:00, Varsity at 6:00) -- use the earliest as the event's
        # start time and keep the full breakdown in the description.
        time_lines = [
            line.replace("\xa0", " ").strip()
            for line in tds[3].get_text("\n", strip=True).split("\n")
            if line.strip()
        ]
        first_time = ""
        if time_lines:
            time_match = TIME_RE.search(time_lines[0])
            first_time = time_match.group(0) if time_match else ""

        symbol = {"Home": "vs", "Away": "@"}.get(home_away, "")
        if sport_short and symbol:
            name = f"{sport_short} {symbol} {opponent}"
        elif sport_short:
            name = f"{sport_short}: {opponent}"
        else:
            name = opponent

        description = "; ".join(filter(None, [home_away, ", ".join(time_lines)]))

        # Full `sport` (not sport_short) because that's the only field
        # that distinguishes e.g. boys vs girls basketball -- two entries
        # can otherwise share date, opponent, and even a blank ("TBD")
        # time, which would collide down to the same slug otherwise.
        slug = re.sub(r"\W+", "-", f"{sport}-{home_away}-{opponent}".lower()).strip("-")

        events.append(
            {
                "name": name,
                "date": current_date.strftime("%Y-%m-%d"),
                "time": first_time,
                # Consistent with how Marceline R-V's own games are tagged
                # elsewhere in this dataset ("Marceline R-V School
                # District | Marceline, MO") regardless of home/away --
                # a Brookfield-only subscriber wants their team's games,
                # not just events physically inside town limits.
                "location": f"Brookfield R-III School District | Brookfield, {CONFIG['state']}",
                "description": description,
                "href": "",
                "event_id": f"bfschools-{current_date.isoformat()}-{slug}",
                "start_iso": None,
                "end_iso": None,
            }
        )

    return events


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
    return f"{key}-{ev['date']}-{time_slug}@{CONFIG['uid_domain']}"


def build_calendar(events):
    cal = Calendar()
    cal.add("prodid", f"-//{CONFIG['county_display_name']} Events Scraper//{CONFIG['uid_domain']}//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", CONFIG["calendar_title"])
    cal.add("x-wr-timezone", CONFIG["timezone"])
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

    brookfield_events = get_brookfield_city_events()
    if brookfield_events:
        print(f"Including {len(brookfield_events)} event(s) from the City of Brookfield's calendar\n")
        events.extend(brookfield_events)

    brookfield_schools_events = get_brookfield_schools_events()
    if brookfield_schools_events:
        print(f"Including {len(brookfield_schools_events)} event(s) from Brookfield R-III's MSHSAA schedule\n")
        events.extend(brookfield_schools_events)

    manual_events = load_manual_events()
    if manual_events:
        print(f"Including {len(manual_events)} approved community-submitted event(s)\n")
        events.extend(manual_events)

    if not events:
        print("No events found -- the page structure may have changed.")
        sys.exit(1)

    print(f"Found {len(events)} events total across all sources\n")
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
