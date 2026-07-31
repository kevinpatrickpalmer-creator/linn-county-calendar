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

Source 3+ -- school districts' game schedules, via MSHSAA:
School districts' actual game schedules often don't live on the
districts' own sites at all -- they're embedded from MSHSAA (Missouri
State High School Activities Association), which hosts a shared
calendar for every Missouri high school by school ID. get_mshsaa_
school_events() is fully generic across schools; MSHSAA_SCHOOLS above
is just this county's list, currently covering 5 of the county's 8
towns directly: Brookfield R-III, Marceline R-V, Bucklin R-II, Linn
County R-I (physically in Purdin, also serves Linneus and Browning),
and Meadville R-IV. CitySpark's own school-district-tagged events are
filtered out in main() to avoid double-listing the same games from two
sources. Laclede appears to have no school of its own left to cover
(its own school closed decades ago with no MSHSAA-listed successor
found); it's still covered by the newspaper and county-government
sources below, just not a school-specific one.

Source 5 -- the newspaper's hand-typed "Community Calendar" page:
A separate WordPress post from the CitySpark widget (source 1) -- staff
type up submissions they receive by email as prose under date headers,
rather than structured fields. It's the only source that covers some
real towns/groups with no other online presence at all (e.g. Laclede
Pershing Days), so it's worth scraping despite being messier: see
get_leader_editorial_calendar_events() for how the messiness (no clean
name/time/location fields, occasional multi-paragraph bullets) is
handled with best-effort heuristics rather than confidently-wrong
extraction. A same-date + shared-keyword check filters out entries that
just duplicate something already captured more cleanly by another
source (e.g. "Wine & Art Stroll" from CitySpark).

Source 6 -- Linn County government's own calendar:
linncomo.com embeds its "Calendar of Events" as a *public* Google
Calendar iframe -- meaning, unlike every other source here, there's no
HTML to scrape at all. Google publishes a standard ICS export for any
public calendar at a predictable URL, so get_linn_county_government_
events() is just a fetch + the same `icalendar` parsing already used
elsewhere in this file. Low volume (courthouse hours, elections, tax
sale) but content no other source has, and the first source to give
Linneus -- the county seat, with zero presence anywhere else in this
system -- any coverage of its own. Also run through the same dedup
check as source 5, since e.g. its "PRIMARY ELECTION" would otherwise
double up with the newspaper's own "Primary Election" entry.

Source 7 -- Rhodes Funeral Home's obituaries (Brookfield):
The one source that isn't upcoming events at all -- recent death
notices instead, dated by date of death/posting rather than the funeral
service date (see RHODES_OBITUARIES_URL comment for why: the service
date is sometimes in the prose but unreliably so, and wrong is worse
than absent for something this consequential). Rhodes serves families
well beyond Linn County, so entries are filtered to a conservative "of
<Linn County town>" match near the start of the bio text -- an
ambiguous entry is excluded rather than risked. Only the last
RHODES_RECENCY_DAYS days are included, since these age out of
relevance quickly unlike the other sources here.

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

# Third+ source: school districts' actual game schedules often don't live
# on the districts' own sites at all -- they're embedded from MSHSAA
# (Missouri State High School Activities Association), which hosts a
# shared calendar for every Missouri high school by school ID. Plain
# server-rendered legacy ASP.NET HTML, no headless browser needed.
# get_mshsaa_school_events() below is fully generic across schools; this
# is just the list of ones this county cares about. Discovered because
# Brookfield had zero CitySpark presence -- then checking Marceline R-V
# (which *does* have some CitySpark presence) found CitySpark was only
# capturing 9 of its 135 real upcoming events, so it's included too, not
# just schools CitySpark completely misses. Linn County R-I is Purdin's
# physical high school but also serves Linneus and Browning (all four
# towns without their own MSHSAA-listed school were checked; Laclede's
# own school appears to have closed decades ago with no current
# successor district found, so it has no MSHSAA entry of its own).
MSHSAA_SCHOOLS = [
    {"school_id": "244", "district": "Brookfield R-III School District", "town": "Brookfield"},
    {"school_id": "354", "district": "Marceline R-V School District", "town": "Marceline"},
    {"school_id": "246", "district": "Bucklin R-II School District", "town": "Bucklin"},
    {"school_id": "346", "district": "Linn County R-I School District", "town": "Purdin"},
    {"school_id": "363", "district": "Meadville R-IV School District", "town": "Meadville"},
]

# Fifth source: the newspaper also runs a hand-typed "Community Calendar"
# page (distinct from the CitySpark widget at CALENDAR_URL) -- staff type
# up submissions they receive by email as plain prose under date headers,
# rather than structured fields. It's the only source covering some real
# community groups/towns that have no other online presence at all (e.g.
# Laclede Pershing Days), so it's worth scraping despite being messier to
# parse than the other sources -- see get_leader_editorial_calendar_events()
# for how that messiness is handled (best-effort, honest degradation
# rather than confidently-wrong extraction).
LEADER_MANUAL_CALENDAR_URL = "https://www.linncountyleader.com/community-calendar-205/"

# Sixth source: Linn County's own government site (linncomo.com) embeds
# its "Calendar of Events" as a *public* Google Calendar iframe -- which
# means, unlike every other source here, there's no HTML to parse at
# all. Google publishes a standard ICS export for any public calendar at
# a predictable URL from its ID, so this is just a fetch + the same
# `icalendar` library already used elsewhere in this file. Low volume
# (courthouse hours, elections, tax sale) but content no other source
# has, and it's the first source to give Linneus -- the county seat
# itself, with zero presence anywhere else in this system -- any
# coverage of its own.
LINN_COUNTY_GOV_ICS_URL = "https://calendar.google.com/calendar/ical/calendar%40linncomo.com/public/basic.ics"

# Seventh source: Rhodes Funeral Home (Brookfield) posts obituaries as a
# JS-rendered list (like CitySpark), but individual obituary pages sit
# behind a Cloudflare bot challenge that blocks plain requests -- the
# listing page itself isn't protected, and it already renders each
# obituary's full text once Playwright loads it, so no detail-page
# fetches are needed at all. Rhodes serves families well beyond Linn
# County (Moberly, Kirksville, etc. all showed up during testing), so
# entries are filtered to only ones whose bio text states "of <Linn
# County town>" near the start -- conservative on purpose: an obituary
# without a clear in-county "of <town>" phrase is excluded even if it's
# probably a real match, since wrongly including an out-of-county
# funeral is worse than missing an ambiguous in-county one. Dated by
# date of death/posting, not the funeral service date -- that's
# sometimes stated in the prose too, but unreliably (often "pending") and
# too consequential to get wrong by guessing, so it's left out entirely;
# these are recent-death notices, not upcoming-event entries, unlike
# every other source here -- only the last RHODES_RECENCY_DAYS count.
RHODES_OBITUARIES_URL = "https://www.rhodesfh.com/obituaries/"
RHODES_RECENCY_DAYS = 21

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


def get_list_html(page, max_attempts=3):
    """The CitySpark widget intermittently fails to load in time (either
    the page navigation itself or the widget's own render) when run from
    GitHub Actions -- transient, and it clears up on a retry within the
    same run rather than indicating anything wrong with the parsing
    logic below. Retrying here means one flaky load doesn't fail the
    whole scheduled workflow (and email everyone) when the other six
    sources would otherwise have succeeded fine."""
    for attempt in range(1, max_attempts + 1):
        try:
            page.goto(CALENDAR_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(".csEvWrap", timeout=20000)
            break
        except Exception as e:
            print(f"  WARNING: CitySpark load attempt {attempt}/{max_attempts} failed: {e}", file=sys.stderr)
            if attempt == max_attempts:
                # Leave evidence behind so a failure in CI (no display to
                # look at) can still be diagnosed after the fact.
                page.screenshot(path="debug_screenshot.png", full_page=True)
                with open("debug_page.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
                raise
            page.wait_for_timeout(3000)

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


def get_mshsaa_school_events(school_id, district, town):
    """Fetch one Missouri school's game schedule from MSHSAA's shared
    calendar (see MSHSAA_SCHOOLS above for why this lives there rather
    than on the district's own site). The page is one big legacy ASP.NET
    grid: a `tr.fs_columnheader` row holds a date, followed by zero or
    more `tr.withBorderBottom` rows (one per matchup) until the next date
    header. A row already in the past carries a `past` class -- skipped
    here in favor of a real date comparison, since relying on the site's
    own "is this past" judgement would silently misbehave if its notion
    of "today" ever drifted from ours. Generic across any Missouri school
    -- only school_id/district/town vary per call."""
    url = f"https://www.mshsaa.org/Shared/CalendarList.aspx?s={school_id}&noheader=1"
    try:
        resp = requests.get(url, headers=BROOKFIELD_REQUEST_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  WARNING: couldn't fetch {district}'s MSHSAA schedule: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    grid = soup.find("table", class_="fs_grid")
    if not grid:
        print(f"  WARNING: MSHSAA schedule page structure has changed for {district} (no fs_grid table found)", file=sys.stderr)
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
                # Tagged by the team's home town regardless of home/away
                # (mirrors how CitySpark itself already tags some of
                # Marceline's games) -- a town-only subscriber wants
                # their team's games, not just events physically inside
                # town limits.
                "location": f"{district} | {town}, {CONFIG['state']}",
                "description": description,
                "href": "",
                "event_id": f"mshsaa-{school_id}-{current_date.isoformat()}-{slug}",
                "start_iso": None,
                "end_iso": None,
            }
        )

    return events


def _find_manual_entry_name_boundary(text, max_len=80):
    """Where a "name" plausibly ends within a hand-typed bullet like
    "Mommy and Me Group, 10-11 a.m., 210 W Hayden St., Marceline. Join
    this..." -- prefers an early comma (the common "Name, detail, detail"
    shape in this data), then falls back to a sentence-ending period,
    skipping periods that are actually abbreviations (a single capital
    letter before them, as in "S.U.P.P.O.R.T."). Returns None if nothing
    plausible is found within max_len, so the caller can fall back to a
    plain truncation instead of confidently returning a wrong answer."""
    comma_idx = text.find(",")
    if 0 < comma_idx <= max_len:
        return comma_idx

    for m in re.finditer(r"\.(?=\s|$)", text[: max_len + 1]):
        idx = m.start()
        before = text[max(0, idx - 2) : idx]
        if before and before[-1].isupper() and (idx < 2 or not text[idx - 2].isalpha()):
            continue  # single capital letter right before the period -> acronym
        return idx

    return None


# This prose almost always writes times as "10:30 a.m." / "7 p.m." (with
# periods), unlike TIME_RE above (used by the CitySpark parser, whose
# source writes "6:30 pm" with no periods) -- a separate regex rather
# than loosening the shared one, so this source's quirks can't change
# CitySpark's already-working behavior.
MANUAL_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s?[ap]\.?m\.?\b", re.IGNORECASE)
MANUAL_HOUR_ONLY_TIME_RE = re.compile(r"(?<!:)\b(\d{1,2})\s?([ap])\.?m\.?\b", re.IGNORECASE)


def _normalize_manual_entry_time(text):
    """Prefers a full "H:MM am/pm" match; falls back to an hour-only one
    ("7 p.m.") common in this hand-typed prose, normalized to "H:00 AM".
    The fallback's negative lookbehind keeps it from misreading the
    minutes of an already-matched "10:30 a.m." as a standalone "30 a.m."."""
    match = MANUAL_TIME_RE.search(text)
    if match:
        compact = match.group(0).upper().replace(".", "").replace(" ", "")
        return f"{compact[:-2]} {compact[-2:]}"
    match = MANUAL_HOUR_ONLY_TIME_RE.search(text)
    if match:
        return f"{match.group(1)}:00 {match.group(2).upper()}M"
    return ""


def get_leader_editorial_calendar_events():
    """Fetch the newspaper's hand-typed "Community Calendar" page -- a
    single WordPress post (not a live database) that editorial staff
    keep editing over time as they receive submissions by email, laid
    out as `<b>Date</b>` headers followed by `<p>` bullets. Two quirks
    this has to handle that the other sources don't: (1) a bullet's text
    sometimes wraps into a second `<p>` with no repeated "*" marker (an
    apparent copy/paste slip on the newspaper's end, not a different
    event) -- treated as a continuation of the previous bullet; and (2)
    there's no structured name/time/location fields at all, just prose,
    so those are extracted with best-effort heuristics that degrade to
    "use the raw text" rather than guessing wrong. No headless browser
    needed -- ordinary WordPress post content, in the raw HTML already."""
    try:
        resp = requests.get(LEADER_MANUAL_CALENDAR_URL, headers=BROOKFIELD_REQUEST_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  WARNING: couldn't fetch the newspaper's manual calendar page: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    content = soup.find("div", class_="entry-content")
    if not content:
        print("  WARNING: manual calendar page structure has changed (no entry-content found)", file=sys.stderr)
        return []

    today = datetime.now(LOCAL_TZ).date()
    current_date = None
    raw_bullets = []  # [{"date": date, "text": str}, ...], in document order

    for p in content.find_all("p", recursive=False):
        bold = p.find("b")
        text = p.get_text(" ", strip=True)
        if not text:
            continue

        if bold:
            date_match = re.match(r"^([A-Za-z]+)\s+(\d{1,2})$", bold.get_text(strip=True))
            current_date = None
            if date_match:
                try:
                    candidate = datetime.strptime(
                        f"{date_match.group(1)} {date_match.group(2)} {today.year}", "%B %d %Y"
                    ).date()
                    # The post has no year in its date headers and gets
                    # edited across a year boundary -- if a date reads as
                    # more than ~2 months in the past, it must mean next
                    # year, not literally the past.
                    if (candidate - today).days < -60:
                        candidate = candidate.replace(year=today.year + 1)
                    current_date = candidate
                except ValueError:
                    current_date = None
            continue

        if current_date is None:
            continue

        if text.startswith("•"):  # "*" bullet marker
            raw_bullets.append({"date": current_date, "text": text[1:].strip()})
        elif raw_bullets and raw_bullets[-1]["date"] == current_date:
            raw_bullets[-1]["text"] += " " + text
        # else: a continuation paragraph with no preceding bullet under
        # this date -- nothing sensible to attach it to, so it's dropped.

    events = []
    for item in raw_bullets:
        text, date = item["text"], item["date"]
        if not text:
            continue

        boundary = _find_manual_entry_name_boundary(text)
        if boundary is not None:
            name = text[:boundary].strip()
        elif len(text) > 80:
            name = text[:77].rsplit(" ", 1)[0] + "..."
        else:
            name = text

        town = next((t for t in CONFIG["towns"] if re.search(rf"\b{re.escape(t)}\b", text)), None)
        location = f"{town}, {CONFIG['state']}" if town else ""

        slug = re.sub(r"\W+", "-", name.lower()).strip("-")[:60]

        events.append(
            {
                "name": name,
                "date": date.strftime("%Y-%m-%d"),
                "time": _normalize_manual_entry_time(text),
                "location": location,
                "description": text,
                "href": "",
                "event_id": f"leadereditorial-{date.isoformat()}-{slug}",
                "start_iso": None,
                "end_iso": None,
            }
        )

    return events


def get_linn_county_government_events():
    """Fetch Linn County government's own calendar via Google Calendar's
    public ICS export -- see LINN_COUNTY_GOV_ICS_URL above for why this
    is the easiest source of the bunch: it's already a standards-format
    .ics file, so this reuses the same `icalendar` parsing the rest of
    this project already relies on (see build_calendar()/send_reminders.py)
    instead of writing new HTML-scraping logic."""
    try:
        resp = requests.get(LINN_COUNTY_GOV_ICS_URL, headers=BROOKFIELD_REQUEST_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  WARNING: couldn't fetch Linn County government's calendar: {e}", file=sys.stderr)
        return []

    try:
        source_cal = Calendar.from_ical(resp.content)
    except ValueError as e:
        print(f"  WARNING: Linn County government's calendar didn't parse as valid ICS: {e}", file=sys.stderr)
        return []

    today = datetime.now(LOCAL_TZ).date()
    events = []

    for vevent in source_cal.walk("VEVENT"):
        dtstart_prop = vevent.get("dtstart")
        name = str(vevent.get("summary", "")).strip()
        if not dtstart_prop or not name:
            continue

        value = dtstart_prop.dt
        all_day = not isinstance(value, datetime)
        if all_day:
            event_date = value
            time_str = ""
        else:
            # Google's export uses UTC ("...Z") timestamps.
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            value = value.astimezone(LOCAL_TZ)
            event_date = value.date()
            time_str = value.strftime("%I:%M %p")

        if event_date < today:
            continue

        uid = str(vevent.get("uid", "")) or re.sub(r"\W+", "-", name.lower()).strip("-")

        events.append(
            {
                "name": name,
                "date": event_date.strftime("%Y-%m-%d"),
                "time": time_str,
                "location": f"Linn County Courthouse | Linneus, {CONFIG['state']}",
                "description": str(vevent.get("description", "")).strip(),
                "href": "",
                "event_id": f"linncogov-{uid}",
                "start_iso": None,
                "end_iso": None,
            }
        )

    return events


def get_rhodes_obituaries_html(page):
    page.goto(RHODES_OBITUARIES_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_selector(".obituaries-list__results li", timeout=20000)
    return page.content()


def parse_rhodes_obituaries(html):
    """Each `<li>` in `.obituaries-list__results` has a `.tribute-dates`
    span (date of death/posting -- "Jul. 09, 2026"), a `.name` link, and
    a `.obituary` paragraph with the full bio text. See the
    RHODES_OBITUARIES_URL comment above for why only the death date is
    used and why in-county filtering is deliberately conservative."""
    soup = BeautifulSoup(html, "html.parser")
    today = datetime.now(LOCAL_TZ).date()
    events = []

    for li in soup.select(".obituaries-list__results li"):
        name_el = li.select_one(".name")
        date_el = li.select_one(".tribute-dates")
        bio_el = li.select_one(".obituary")
        if not name_el or not date_el or not bio_el:
            continue

        name = name_el.get_text(strip=True)
        bio = bio_el.get_text(" ", strip=True)

        try:
            death_date = datetime.strptime(date_el.get_text(strip=True).replace(".", ""), "%b %d, %Y").date()
        except ValueError:
            continue
        if not (0 <= (today - death_date).days <= RHODES_RECENCY_DAYS):
            continue

        town = next(
            (t for t in CONFIG["towns"] if re.search(rf"\bof\s+{re.escape(t)}\b", bio[:200])),
            None,
        )
        if not town:
            continue  # no confident in-county residence found -- excluded on purpose

        href = name_el.get("href", "")
        if href and not href.startswith("http"):
            href = f"https://www.rhodesfh.com{href}"

        events.append(
            {
                "name": f"Obituary: {name}",
                "date": death_date.strftime("%Y-%m-%d"),
                "time": "",
                "location": f"{town}, {CONFIG['state']}",
                "description": f"{bio}\n\nFull obituary and service details: {href}" if href else bio,
                "href": "",
                "event_id": f"rhodesobit-{death_date.isoformat()}-{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}",
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

        # Rhodes' site appears to challenge/block traffic from GitHub
        # Actions' well-known CI IP ranges even though the same request
        # works fine from a residential IP -- a real, observed failure
        # in production, not a hypothetical. A failure here must not
        # take down the other six working sources, so it's caught and
        # logged rather than left to propagate and crash the whole run.
        try:
            rhodes_html = get_rhodes_obituaries_html(page)
            rhodes_events = parse_rhodes_obituaries(rhodes_html)
        except Exception as e:
            print(f"  WARNING: couldn't fetch Rhodes Funeral Home's obituaries: {e}", file=sys.stderr)
            rhodes_events = []

        browser.close()

    # MSHSAA now covers every school district's games directly and far
    # more completely than CitySpark ever did (see MSHSAA_SCHOOLS above)
    # -- drop CitySpark's own school-district-tagged entries so the same
    # game doesn't show up twice, once from each source. CitySpark's
    # other, non-school content for these towns (city council, trash
    # collection, library, etc.) is untouched.
    mshsaa_district_prefixes = tuple(f"{s['district']} |" for s in MSHSAA_SCHOOLS)
    events = [ev for ev in events if not ev["location"].startswith(mshsaa_district_prefixes)]

    brookfield_events = get_brookfield_city_events()
    if brookfield_events:
        print(f"Including {len(brookfield_events)} event(s) from the City of Brookfield's calendar\n")
        events.extend(brookfield_events)

    for school in MSHSAA_SCHOOLS:
        school_events = get_mshsaa_school_events(**school)
        if school_events:
            print(f"Including {len(school_events)} event(s) from {school['district']}'s MSHSAA schedule\n")
            events.extend(school_events)

    # The newspaper's hand-typed calendar inevitably covers some of the
    # same real-world events already captured more cleanly above (e.g.
    # "Wine & Art Stroll" from CitySpark vs. "Marceline Wine and Art
    # Stroll..." here) -- there's no shared ID to dedupe on like there
    # was for MSHSAA, so this is a same-date + shared-significant-word
    # heuristic instead. Conservative on purpose: it'll let a few real
    # duplicates through rather than risk dropping a genuinely distinct
    # event that just happens to share a date and a common word.
    STOPWORDS = {
        "the", "and", "for", "with", "from", "this", "that", "will", "are",
        "a", "an", "at", "in", "of", "on", "to", "vs", "is", "be", "or",
        # Words common across many unrelated events in *this* dataset
        # specifically -- "Linn" and "County" appear on nearly everything
        # in a Linn County calendar, so on their own they're not a
        # meaningful signal that two events are the same one.
        "linn", "county", "community", "annual",
    }

    def significant_words(name):
        return {w for w in re.findall(r"[a-z0-9']+", name.lower()) if len(w) > 2 and w not in STOPWORDS}

    events_by_date = {}
    for ev in events:
        events_by_date.setdefault(ev["date"], []).append(significant_words(ev["name"]))

    def is_likely_duplicate(candidate):
        candidate_words = significant_words(candidate["name"])
        if not candidate_words:
            return False
        return any(len(candidate_words & existing) >= 2 for existing in events_by_date.get(candidate["date"], []))

    def add_with_dedup(new_events, label):
        """Filters new_events against events_by_date (which reflects
        everything gathered so far), extends both `events` and the index
        with whatever survives, and prints a summary line. Applied to
        each additional source in turn so e.g. the county government's
        "PRIMARY ELECTION" can be caught as a duplicate of the
        newspaper's own "Primary Election" entry, not just of the
        earlier, more-structured sources."""
        deduped = [ev for ev in new_events if not is_likely_duplicate(ev)]
        skipped = len(new_events) - len(deduped)
        print(
            f"Including {len(deduped)} event(s) from {label}"
            f"{f' ({skipped} skipped as likely duplicates of events above)' if skipped else ''}\n"
        )
        events.extend(deduped)
        for ev in deduped:
            events_by_date.setdefault(ev["date"], []).append(significant_words(ev["name"]))

    add_with_dedup(get_leader_editorial_calendar_events(), "the newspaper's manual calendar page")
    add_with_dedup(get_linn_county_government_events(), "Linn County government's calendar")
    add_with_dedup(rhodes_events, "Rhodes Funeral Home (in-county obituaries)")

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
