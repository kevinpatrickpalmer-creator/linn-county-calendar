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

Source 7, 8, 9 -- funeral home obituaries (Brookfield, Marceline):
The only sources that aren't upcoming events -- recent death notices
instead, dated by date of death/posting rather than the funeral service
date (see OBITUARY_RECENCY_DAYS comment for why: the service date is
sometimes in the prose but unreliably so, and wrong is worse than
absent for something this consequential). Rhodes needs Playwright
(JS-rendered, and detail pages are Cloudflare-protected); Wright and
Delaney run the same third-party platform and need no browser at all
(a plain XML sitemap plus JSON-LD on each page) --
get_tribute_technology_obituaries() is fully generic across any
funeral home on that platform. All three serve families well beyond
Linn County, so entries are filtered to a conservative in-county town
match -- an ambiguous entry is excluded rather than risked.

Source 10 -- Brookfield Area Chamber of Commerce community events:
The Chamber's site also serves as the shared calendar for Main Street
Brookfield and the Brookfield Area Growth Partnership (all three are
the same umbrella organization, just different public-facing brands),
and runs the same "Events Calendar WD" WordPress plugin as the City of
Brookfield's own site (source 2) -- same schema.org Event JSON-LD per
page, just discovered via WordPress's own built-in sitemap instead of
a dedicated ecwd_event-sitemap.xml. Real, actively-maintained content
distinct from both CitySpark and the city's own calendar: Railroad
Days, the Great Pershing Balloon Derby, Main Street Sip & Stroll, and
smaller recurring things like Linn County Health Department programs
hosted in Brookfield. Unlike the city's own calendar, not every event
here is necessarily inside Brookfield itself (the chamber occasionally
lists a neighboring town's event, e.g. a rivalry game hosted in
Marceline) -- see get_brookfield_chamber_events() for how the town is
parsed from each event's own street address rather than assumed.

Source 11 -- Downtown Marceline Foundation's calendar:
downtownmarceline.org embeds its events calendar the same way Linn
County government's does (source 6) -- a *public* Google Calendar
iframe, so there's no HTML to scrape at all, just Google's standard ICS
export. get_downtown_marceline_events() is deliberately its own
function rather than a shared helper with
get_linn_county_government_events(), even though both fetch+parse a
public Google Calendar the same way: this one preserves each event's
own LOCATION field (a real street address) rather than assuming one
fixed venue, since the Foundation's calendar covers real venues around
town rather than always the same courthouse -- forcing that difference
through one shared function would need a callback for one call site
alone. Genuinely new Marceline content beyond what CitySpark and the
newspaper's page already capture -- Patriotic Pie War, the Spring
Festival, Shop Hop, the library's own Quarter Auction fundraiser -- even
though CitySpark is itself Marceline-based (source 1), it was already
found to only capture a fraction of Marceline's real event volume (see
the MSHSAA_SCHOOLS comment above). Run through the same dedup check as
the newspaper's page, since e.g. its "Wine & Art Stroll" would
otherwise double up with CitySpark's own entry for the same event.

Source 12 -- Teter Auction Company:
The only auction/estate-sale house found with real, ongoing in-county
content -- physically headquartered in Laclede, and its homepage lists
real land/estate auctions across the region, including ones in Laclede
and Brookfield specifically. Unlike every other source here, though,
there's no structured markup to lean on at all: no schema.org JSON-LD,
no semantic class names, just free-form Wix rich-text blocks. Several
other local auction companies were checked (Sayre, Smith, Scotty's,
McCurdy, Enyeart) and none had both real in-county content and
anything more structured to scrape -- and a national estate-sale
aggregator (estatesales.net) currently has zero listings anywhere near
Linn County, so isn't a viable source either. get_teter_auction_events()
is a best-effort text parser in the same spirit as
get_leader_editorial_calendar_events() -- it reads the page's own
rendered text line-by-line rather than its markup, splitting on each
"TOWN, MISSOURI" header, and is deliberately conservative: a block
whose town isn't one of ours, or whose date can't be confidently
parsed, is skipped outright rather than guessed at. This is the most
fragile source in this file by far -- a homepage redesign could break
it silently -- but it's also the only realistic way to get this
content, since auction companies this size don't tend to adopt a
submission form on their own.

Each source's output gets normalized to the same event dict shape before
merging, so adding another town's source later just means writing one
more `get_*_events()` function and extending it into `events` in main() --
build_calendar(), event_uid(), etc. need no changes per source.

Besides the merged docs/linn_county_events.ics, main() also writes one
filtered .ics per town to docs/towns/ (see write_town_ics_files()) so
someone can subscribe their phone/computer calendar to just their own
town instead of always getting the whole county. extract_town(), the
same town-matching logic calendar-view.html's JS and
send_reminders.py's per-town email filtering already used, now lives in
calendar_config.py so all three stay in sync.

Everything that differs between deployments (timezone, calendar display
name, UID namespace) lives in docs/config.json, loaded via
calendar_config.py. The source URLs and scraping/parsing logic below are
specific to these particular sites and aren't config-driven -- a new
town/county needs its own source scrapers unless its sources happen to
run the same platforms (CitySpark, "Events Calendar WD", etc.).

Install:
    pip install playwright beautifulsoup4 icalendar requests python-dateutil
    playwright install chromium

Run:
    python scrape_linn_county_calendar.py
"""
import glob
import html
import itertools
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
    from dateutil.rrule import rrule, WEEKLY, MONTHLY, MO, TU, WE, TH, FR, SA, SU
except ImportError:
    print(
        "The `python-dateutil` package isn't installed.\n"
        "Install with:\n"
        "    pip install python-dateutil"
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

from calendar_config import extract_town, load_config

CONFIG = load_config()

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")

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

# Eleventh source: the Downtown Marceline Foundation's own calendar,
# embedded on downtownmarceline.org the same way (a public Google
# Calendar iframe) -- see the module docstring's "Source 11" section for
# why get_downtown_marceline_events() is its own function rather than
# sharing one with get_linn_county_government_events() above despite
# both being Google Calendar exports.
DOWNTOWN_MARCELINE_ICS_URL = (
    "https://calendar.google.com/calendar/ical/"
    "c_519a86074d6a3267a04609eb6bb3da5711e0049de867055e60b1b1867168ffc9"
    "%40group.calendar.google.com/public/basic.ics"
)

# Twelfth source: Teter Auction Company's homepage lists real, current
# auctions -- see the module docstring's "Source 12" section for why
# get_teter_auction_events() has to parse the page's own rendered text
# rather than any structured markup. Auctions draw people well beyond
# their own town in a way most other events here don't -- people
# already treat them as worth an out-of-county drive -- so this source
# widens its town match beyond CONFIG["towns"] to include neighboring
# Macon and Chillicothe (both along the same Highway 36 corridor, per
# CLAUDE.md's brand context) rather than only the 8 Linn County towns
# every other source is limited to. Since extract_town() has no notion
# of a fixed town list -- it just pulls whatever "Town, ST" text
# appears -- these still correctly show up in the whole-county
# calendar without appearing in any single Linn County town's own
# filtered .ics, which is what should happen for towns that aren't
# actually in Linn County.
TETER_AUCTION_URL = "https://www.teterauction.com/"
TETER_AUCTION_EXTRA_TOWNS = ("Macon", "Chillicothe")
TETER_TOWN_HEADER_RE = re.compile(r"^([A-Z][A-Z .]+), MISSOURI$")
TETER_DATE_RE = re.compile(
    r"^(?:Opens:\s*)?([A-Za-z]+, [A-Za-z]+ \d{1,2}, \d{4})\s*\S\s*(\d{1,2}:\d{2}\s?[AP]M)$"
)

# Obituary sources (7, 8): recent death notices, not upcoming events like
# everywhere else here -- dated by date of death/posting, not the funeral
# service date (sometimes stated in the prose too, but unreliably --
# often "pending" -- and too consequential to get wrong by guessing, so
# it's left out entirely). Only the last OBITUARY_RECENCY_DAYS count,
# since these age out of relevance quickly. Both funeral homes serve
# families well beyond Linn County, so entries are filtered to ones
# whose bio text names a Linn County town near the death/residence
# mention -- conservative on purpose: an obituary without a clear
# in-county match is excluded even if it's probably a real match, since
# wrongly including an out-of-county funeral is worse than missing an
# ambiguous in-county one.
OBITUARY_RECENCY_DAYS = 21

# Seventh source: Rhodes Funeral Home (Brookfield) posts obituaries as a
# JS-rendered list (like CitySpark), but individual obituary pages sit
# behind a Cloudflare bot challenge that blocks plain requests -- the
# listing page itself isn't protected, and it already renders each
# obituary's full text once Playwright loads it, so no detail-page
# fetches are needed at all.
RHODES_OBITUARIES_URL = "https://www.rhodesfh.com/obituaries/"

# Eighth+ source: Wright Funeral Home and Delaney Funeral Home (also
# Brookfield/Marceline) both run the same third-party platform (Tribute
# Technology) with no Cloudflare protection anywhere -- an XML sitemap
# lists every obituary permalink with a lastmod date, and each obituary
# page embeds a clean schema.org Person JSON-LD block (birthDate/
# deathDate/description). No headless browser needed at all, unlike
# Rhodes: both URL discovery and page content are plain HTML.
# get_tribute_technology_obituaries() is fully generic across any
# funeral home on this platform; TRIBUTE_TECHNOLOGY_FUNERAL_HOMES below
# is just this county's list. Only sitemap entries with a recent
# lastmod are fetched, to avoid pulling hundreds of historical
# obituaries just to find the handful of recent ones. Delaney has
# locations in both Marceline and Bucklin.
TRIBUTE_TECHNOLOGY_FUNERAL_HOMES = [
    {
        "name": "Wright Funeral Home",
        "base_url": "https://www.wright-funeralhome.com",
    },
    {
        "name": "Delaney Funeral Home",
        "base_url": "https://www.delaneyfuneralhome.com",
    },
]

# Tenth source: the Brookfield Area Chamber of Commerce runs the same
# "Events Calendar WD" plugin as the City of Brookfield's own site
# (BROOKFIELD_CITY_BASE above) -- same schema.org Event JSON-LD per
# event page, just discovered via WordPress core's own built-in sitemap
# (small enough, ~65 events total, that it's a single unpaginated file)
# rather than a dedicated ecwd_event-sitemap.xml. See the module
# docstring's "Source 10" section for why this is worth a separate
# scraper from CitySpark and the city's own calendar.
BROOKFIELD_CHAMBER_BASE = "https://brookfieldmochamber.com"
BROOKFIELD_CHAMBER_SITEMAP_URL = f"{BROOKFIELD_CHAMBER_BASE}/wp-sitemap-posts-ecwd_event-1.xml"

TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s?[ap]m\b", re.IGNORECASE)
EVENT_ID_RE = re.compile(r"#/details/[^/]+/(\d+)/")
LOCAL_TZ = ZoneInfo(CONFIG["timezone"])
# Written into docs/ so GitHub Pages (serving from /docs) can host it directly.
ICS_PATH = "docs/linn_county_events.ics"
# Event categories a subscriber can opt out of individually via
# checkboxes on index.html (e.g. someone who wants their town's events
# but not school sports games or obituaries) -- see the "category" key
# each event dict may carry (get_mshsaa_school_events() tags "sports";
# the funeral home sources tag "obituary") and
# _write_category_variant_ics_files() below, which writes one .ics per
# combination of these to exclude, alongside the "everything included"
# file every caller already writes. Adding a third category later is
# just adding it here -- the combination logic doesn't change.
FILTERABLE_CATEGORIES = ("sports", "obituary")
# Per-source health snapshot from the most recent run -- see
# docs/status.html and the source_health comment in main() for details.
SOURCE_STATUS_PATH = "docs/source_status.json"
# One filtered .ics per town, alongside the full one, so someone can
# subscribe their phone/computer calendar to just their own town instead
# of always getting the whole county -- see write_town_ics_files() in
# main(). docs/calendar-view.html's town filter and send_reminders.py's
# per-town email filtering both already existed; this is the same idea
# applied to the actual calendar subscription itself.
TOWN_ICS_DIR = "docs/towns"
DEFAULT_DURATION = timedelta(hours=1)
# One JSON file per community-submitted event that's been approved (see
# docs/admin.html). Rejected/pending submissions never get a file here, so
# they structurally can't reach the .ics -- there's no "is it approved?"
# check to get wrong.
MANUAL_EVENTS_DIR = "data/manual_events"


def dismiss_cookie_banner(page):
    """linncountyleader.com added a cookie-consent overlay (the
    vanilla-cookieconsent library, recognizable by its #c-p-bn/#c-s-bn
    button ids) that blocks the CitySpark widget's own script from ever
    rendering .csEvWrap tiles until a choice is made -- confirmed by hand
    on 2026-08-29 (0 events found for an entire run) -- clicking either
    button unblocks it, so this picks "Accept necessary" as the more
    privacy-respecting option. Silently does nothing if the banner isn't
    present (a returning visitor's consent may already be recorded, or
    the site could remove the banner entirely later)."""
    try:
        page.click("#c-s-bn", timeout=4000)
    except Exception:
        pass


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
            dismiss_cookie_banner(page)
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


# Indexed by date.weekday() (Monday=0) so a start date's own weekday can
# be turned into the dateutil constant _expand_manual_event_dates() needs
# for "the 3rd Monday of the month"-style recurrence.
_WEEKDAY_CONSTANTS = (MO, TU, WE, TH, FR, SA, SU)


def _expand_manual_event_dates(data, start_date):
    """A manually-submitted event can optionally repeat (see submit.html's
    "Repeats?" field) rather than requiring someone to resubmit a monthly
    meeting by hand forever -- this is what a local political party's
    "3rd Monday of every month" meeting needs, for instance. Expanded
    here into plain, independent dates -- the same one-date-per-event
    shape every other source already produces -- rather than an ICS
    RRULE, since calendar-view.html's own client-side parser and the
    per-town splitting in write_town_ics_files() both work off
    individual dated events with no notion of a recurrence rule.
    Unrecognized or incomplete recurrence data degrades to a single
    one-off occurrence on start_date rather than guessing."""
    recurrence = (data.get("recurrence") or "none").strip()
    if recurrence == "none":
        return [start_date]

    try:
        until = datetime.strptime((data.get("repeat_until") or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return [start_date]
    if until < start_date:
        return [start_date]

    if recurrence == "weekly":
        occurrences = rrule(WEEKLY, dtstart=start_date, until=until)
    elif recurrence == "biweekly":
        occurrences = rrule(WEEKLY, interval=2, dtstart=start_date, until=until)
    elif recurrence == "monthly_weekday":
        # e.g. the 3rd Monday of the month, matching the start date's own
        # week-of-month -- computed fresh each month via dateutil rather
        # than approximated by adding ~30 days, so it can't drift onto
        # the wrong week.
        ordinal = (start_date.day - 1) // 7 + 1
        weekday = _WEEKDAY_CONSTANTS[start_date.weekday()](ordinal)
        occurrences = rrule(MONTHLY, byweekday=weekday, dtstart=start_date, until=until)
    elif recurrence == "monthly_date":
        occurrences = rrule(MONTHLY, bymonthday=start_date.day, dtstart=start_date, until=until)
    else:
        return [start_date]

    dates = [o.date() for o in occurrences]
    return dates or [start_date]


def _manual_event_iso_range(occurrence_date, time_str, end_time_str):
    """Manually submitted events can optionally include an end time (see
    the "End time" field on submit.html/admin.html); when both a start and
    end time are given, this turns them into real ISO datetimes so
    build_calendar() uses the event's actual length instead of falling
    back to DEFAULT_DURATION for every manual submission."""
    if not time_str or not end_time_str:
        return None, None
    date_str = occurrence_date.strftime("%Y-%m-%d")
    try:
        start_dt = datetime.strptime(f"{date_str} {time_str.upper()}", "%Y-%m-%d %I:%M %p").replace(tzinfo=LOCAL_TZ)
        end_dt = datetime.strptime(f"{date_str} {end_time_str.upper()}", "%Y-%m-%d %I:%M %p").replace(tzinfo=LOCAL_TZ)
    except ValueError:
        return None, None
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)  # e.g. a dance running 9pm-1am
    return start_dt.isoformat(), end_dt.isoformat()


def load_manual_events():
    """Load community-submitted events that have been approved (see
    docs/admin.html for how a file lands here). Each file becomes one or
    more events (see _expand_manual_event_dates() for the optional
    recurrence case), in the same shape parse_events() produces, so
    build_calendar() and event_uid() need no special-casing for them --
    event_uid() already folds each occurrence's own date into its UID, so
    reusing the same event_id across every occurrence of one recurring
    entry is safe. A malformed file is skipped with a warning rather than
    failing the whole run -- one bad manual entry shouldn't take down the
    scraped events too."""
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
        date_str = (data.get("date") or "").strip()
        if not name or not date_str:
            print(f"  WARNING: skipping {path}, missing required name/date", file=sys.stderr)
            continue

        try:
            start_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            print(f"  WARNING: skipping {path}, unparseable date {date_str!r}", file=sys.stderr)
            continue

        time_str = (data.get("time") or "").strip()
        end_time_str = (data.get("end_time") or "").strip()

        for occurrence_date in _expand_manual_event_dates(data, start_date):
            start_iso, end_iso = _manual_event_iso_range(occurrence_date, time_str, end_time_str)
            manual_events.append(
                {
                    "name": name,
                    "date": occurrence_date.strftime("%Y-%m-%d"),
                    "time": time_str,
                    "location": (data.get("location") or "").strip(),
                    "description": (data.get("description") or "").strip(),
                    "href": "",  # no CitySpark detail page to fetch
                    "event_id": f"manual-{slug}",
                    "start_iso": start_iso,
                    "end_iso": end_iso,
                    "event_type": (data.get("event_type") or "").strip(),
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


def get_brookfield_chamber_events():
    """Fetch every event from the Brookfield Area Chamber of Commerce's
    calendar via WordPress's own built-in sitemap (see
    BROOKFIELD_CHAMBER_SITEMAP_URL above) -- the same "Events Calendar WD"
    plugin and JSON-LD shape as get_brookfield_city_events(), just a
    different sitemap path and, unlike that function, not allowed to
    assume every event is physically in Brookfield: the town is parsed
    out of each event's own street address instead, falling back to
    Brookfield (the chamber's own home base) only when the address
    doesn't clearly name a different county town."""
    try:
        resp = requests.get(
            BROOKFIELD_CHAMBER_SITEMAP_URL,
            headers=BROOKFIELD_REQUEST_HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  WARNING: couldn't fetch the Brookfield Chamber's event sitemap: {e}", file=sys.stderr)
        return []

    sitemap_soup = BeautifulSoup(resp.content, "html.parser")
    event_urls = [loc.get_text(strip=True) for loc in sitemap_soup.find_all("loc")]

    town_re = re.compile(
        rf"\b({'|'.join(re.escape(t) for t in CONFIG['towns'])}),\s*{re.escape(CONFIG['state'])}\b"
    )

    today = datetime.now(LOCAL_TZ).date()
    events = []
    for i, url in enumerate(event_urls, 1):
        print(f"  checking Brookfield Chamber event {i}/{len(event_urls)}...", end="\r", file=sys.stderr)
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

        place = data.get("location") or {}
        venue = (place.get("name") or "").strip()
        street_address = ((place.get("address") or {}).get("streetAddress") or "")
        town_match = town_re.search(street_address)
        town = town_match.group(1) if town_match else "Brookfield"
        location = f"{venue} | {town}, {CONFIG['state']}" if venue else f"{town}, {CONFIG['state']}"

        slug = url.rstrip("/").rsplit("/", 1)[-1]

        events.append(
            {
                "name": (data.get("name") or "").strip(),
                "date": start.strftime("%Y-%m-%d"),
                "time": start.strftime("%I:%M %p"),
                "location": location,
                "description": (data.get("description") or "").strip(),
                "href": "",
                "event_id": f"bfchamber-{slug}",
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
                # See FILTERABLE_CATEGORIES -- lets a subscriber uncheck
                # "School sports games" on index.html and get every
                # "-no-sports*.ics" variant _write_category_variant_ics_files()
                # writes. A handful of sports-ish events from other
                # sources (e.g. the Chamber's own "Bell Game") aren't
                # caught by this; tagging by source is reliable, tagging
                # by guessing at event names is not.
                "category": "sports",
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


def get_downtown_marceline_events():
    """Fetch the Downtown Marceline Foundation's calendar via Google
    Calendar's public ICS export -- see DOWNTOWN_MARCELINE_ICS_URL above.
    Structurally the same fetch+parse as
    get_linn_county_government_events() just above, but this calendar's
    own LOCATION field is a real, worth-preserving street address (e.g.
    "327 S Kansas Ave, Marceline, MO 64658, USA") rather than always the
    same courthouse, so every event here is tagged Marceline but keeps
    whatever venue address Google gives it."""
    try:
        resp = requests.get(DOWNTOWN_MARCELINE_ICS_URL, headers=BROOKFIELD_REQUEST_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  WARNING: couldn't fetch the Downtown Marceline Foundation's calendar: {e}", file=sys.stderr)
        return []

    try:
        source_cal = Calendar.from_ical(resp.content)
    except ValueError as e:
        print(f"  WARNING: the Downtown Marceline Foundation's calendar didn't parse as valid ICS: {e}", file=sys.stderr)
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

        # The street address alone (before the first comma) reads fine as
        # a venue; falls back to a bare "Marceline, ST" for entries with
        # no LOCATION at all (e.g. a plain "Board Meeting").
        raw_location = str(vevent.get("location", "")).strip()
        venue = raw_location.split(",")[0].strip() if raw_location else ""
        location = f"{venue} | Marceline, {CONFIG['state']}" if venue else f"Marceline, {CONFIG['state']}"

        uid = str(vevent.get("uid", "")) or re.sub(r"\W+", "-", name.lower()).strip("-")

        events.append(
            {
                "name": name,
                "date": event_date.strftime("%Y-%m-%d"),
                "time": time_str,
                "location": location,
                "description": str(vevent.get("description", "")).strip(),
                "href": "",
                "event_id": f"dtmarceline-{uid}",
                "start_iso": None,
                "end_iso": None,
            }
        )

    return events


def get_teter_auction_events():
    """Fetch Teter Auction Company's homepage and parse its "Upcoming
    Auctions" list from the page's own rendered text (see
    TETER_AUCTION_URL above for why -- there's no structured markup to
    lean on at all). Each auction block starts with an all-caps
    "TOWN, MISSOURI" header; only blocks whose town matches one of ours
    are kept, since most of Teter's real auctions are elsewhere in the
    region. A block whose date can't be confidently parsed is skipped
    rather than guessed at, same principle as everywhere else in this
    file."""
    try:
        resp = requests.get(TETER_AUCTION_URL, headers=BROOKFIELD_REQUEST_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  WARNING: couldn't fetch Teter Auction Company's homepage: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    text = (soup.find("main") or soup).get_text("\n", strip=True)

    start = text.find("UPCOMING AUCTIONS")
    if start == -1:
        print("  WARNING: Teter Auction Company's page structure has changed (no 'UPCOMING AUCTIONS' section found)", file=sys.stderr)
        return []
    end = text.find("Never miss another auction", start)
    section = text[start + len("UPCOMING AUCTIONS") : end if end != -1 else None]

    # Split into one block per "TOWN, MISSOURI" header line -- everything
    # after a header, up to the next one, belongs to that auction.
    blocks = []
    current = None
    for line in section.split("\n"):
        line = line.strip()
        if not line or line == "​":  # Wix leaves a stray zero-width space per block
            continue
        header_match = TETER_TOWN_HEADER_RE.match(line)
        if header_match:
            if current:
                blocks.append(current)
            current = {"town_header": header_match.group(1).title(), "lines": []}
        elif current is not None:
            current["lines"].append(line)
    if current:
        blocks.append(current)

    today = datetime.now(LOCAL_TZ).date()
    events = []
    for block in blocks:
        town = next(
            (
                t
                for t in (*CONFIG["towns"], *TETER_AUCTION_EXTRA_TOWNS)
                if t.lower() == block["town_header"].lower()
            ),
            None,
        )
        if not town:
            continue  # not one of our towns (or Macon/Chillicothe) -- most Teter auctions are elsewhere

        lines = block["lines"]
        if not lines:
            continue
        name = lines[0]

        date_idx, start_dt = None, None
        for i, line in enumerate(lines):
            date_match = TETER_DATE_RE.match(line)
            if date_match:
                try:
                    start_dt = datetime.strptime(
                        f"{date_match.group(1)} {date_match.group(2).upper().replace(' ', '')}",
                        "%A, %B %d, %Y %I:%M%p",
                    ).replace(tzinfo=LOCAL_TZ)
                except ValueError:
                    continue
                date_idx = i
                break
        if start_dt is None or start_dt.date() < today:
            continue

        # Everything between the date line and the final "VIEW AUCTION
        # DETAILS"/"DETAILS COMING SOON!" line is the address -- joined,
        # then trimmed of the trailing ", Town, MO #####" the block's own
        # header already told us, rather than re-parsed from it.
        address_lines = lines[date_idx + 1 : -1] if len(lines) > date_idx + 1 else []
        address = " ".join(address_lines).replace("Address:", "").strip()
        address = re.sub(
            rf",?\s*{re.escape(town)},?\s*(Missouri|MO)?\.?\s*\d{{0,5}}\.?$",
            "",
            address,
            flags=re.IGNORECASE,
        ).strip().rstrip(",")

        location = f"{address} | {town}, {CONFIG['state']}" if address else f"{town}, {CONFIG['state']}"
        slug = re.sub(r"[^a-z0-9]+", "-", f"{name}-{town}".lower()).strip("-")

        events.append(
            {
                "name": name,
                "date": start_dt.strftime("%Y-%m-%d"),
                "time": start_dt.strftime("%I:%M %p"),
                "location": location,
                "description": f"See {TETER_AUCTION_URL} for full auction details.",
                "href": "",
                "event_id": f"teterauction-{start_dt.date().isoformat()}-{slug}",
                "start_iso": None,
                "end_iso": None,
            }
        )

    return events


def get_rhodes_obituaries_html(page, max_attempts=3):
    """Retries transient load failures the same way get_list_html() does
    for CitySpark above -- confirmed by hand on 2026-08-29 that a plain,
    unhurried load of this page works fine (12 obituaries rendered with
    no cookie banner or other blocker in the way), so a single timeout in
    CI most likely means the page was just slow that once, not that
    something structural broke."""
    for attempt in range(1, max_attempts + 1):
        try:
            page.goto(RHODES_OBITUARIES_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(".obituaries-list__results li", timeout=20000)
            return page.content()
        except Exception as e:
            print(f"  WARNING: Rhodes load attempt {attempt}/{max_attempts} failed: {e}", file=sys.stderr)
            if attempt == max_attempts:
                page.screenshot(path="debug_screenshot_rhodes.png", full_page=True)
                with open("debug_page_rhodes.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
                raise
            page.wait_for_timeout(3000)


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
        if not (0 <= (today - death_date).days <= OBITUARY_RECENCY_DAYS):
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
                "category": "obituary",
            }
        )

    return events


def _find_town_near_death_mention(bio, before=100, after=150):
    """Different funeral homes -- and even different obituaries on the
    same site, presumably depending on who in the family wrote it up --
    place the residence town in different spots relative to "passed
    away"/"died": sometimes before ("<Name>, age, of <town>, MO; passed
    away...") and sometimes after ("<Name> passed away ... in <town>,
    MO"). This checks a window on both sides of the death mention rather
    than assuming one fixed order, and skips a match if it's preceded by
    "formerly"/"previously" -- e.g. "of Marceline, formerly of Mendon,
    passed away..." should match Marceline, not Mendon, since "formerly
    of" explicitly means that's not where they lived anymore."""
    death_match = re.search(r"passed away|died", bio, re.IGNORECASE)
    if not death_match:
        return None
    window = bio[max(0, death_match.start() - before) : death_match.start() + after]
    for town in CONFIG["towns"]:
        for m in re.finditer(rf"\b(?:of|in)\s+{re.escape(town)}\b", window):
            preceding = window[: m.start()].rstrip()
            if re.search(r"\b(?:formerly|previously|formally)$", preceding, re.IGNORECASE):
                continue
            return town
    return None


def get_tribute_technology_obituaries(name, base_url):
    """Fetch recent obituaries from a funeral home running the Tribute
    Technology platform (see TRIBUTE_TECHNOLOGY_FUNERAL_HOMES above for
    why no headless browser is needed here, unlike Rhodes). Each
    sitemap entry's <lastmod> is used only to cheaply skip old
    obituaries before fetching anything; the authoritative date is the
    deathDate pulled from each page's own schema.org Person JSON-LD
    block. Generic across any funeral home on this platform -- only
    name/base_url vary per call."""
    today = datetime.now(LOCAL_TZ).date()
    candidate_urls = []

    for sitemap_path in ("obituaries-sitemap/1.xml.gz", "obituaries-sitemap/2.xml.gz"):
        sitemap_url = f"{base_url}/{sitemap_path}"
        try:
            resp = requests.get(sitemap_url, headers=BROOKFIELD_REQUEST_HEADERS, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  WARNING: couldn't fetch {name}'s sitemap {sitemap_url}: {e}", file=sys.stderr)
            continue
        for loc, lastmod in re.findall(r"<loc>([^<]+)</loc><lastmod>([^<]+)</lastmod>", resp.text):
            try:
                mod_date = datetime.strptime(lastmod, "%Y-%m-%d").date()
            except ValueError:
                continue
            if 0 <= (today - mod_date).days <= OBITUARY_RECENCY_DAYS:
                candidate_urls.append(loc)

    id_prefix = re.sub(r"[^a-z0-9]+", "", name.lower())
    events = []
    for url in candidate_urls:
        try:
            page = requests.get(url, headers=BROOKFIELD_REQUEST_HEADERS, timeout=30)
            page.raise_for_status()
        except requests.RequestException:
            continue

        data = None
        for match in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', page.text, re.DOTALL):
            try:
                candidate = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            if candidate.get("@type") == "Person":
                data = candidate
                break
        if not data:
            continue

        person_name = html.unescape(data.get("name") or "").strip()
        try:
            death_date = datetime.strptime((data.get("deathDate") or "").strip(), "%B %d, %Y").date()
        except ValueError:
            continue
        if not (0 <= (today - death_date).days <= OBITUARY_RECENCY_DAYS):
            continue

        bio_html = html.unescape(data.get("description") or "")
        bio = BeautifulSoup(bio_html, "html.parser").get_text(" ", strip=True)

        town = _find_town_near_death_mention(bio)
        if not town:
            continue  # no confident in-county residence found -- excluded on purpose

        events.append(
            {
                "name": f"Obituary: {person_name}",
                "date": death_date.strftime("%Y-%m-%d"),
                "time": "",
                "location": f"{town}, {CONFIG['state']}",
                "description": f"{bio}\n\nFull obituary and service details: {url}",
                "href": "",
                "event_id": f"{id_prefix}obit-{death_date.isoformat()}-{re.sub(r'[^a-z0-9]+', '-', person_name.lower()).strip('-')}",
                "start_iso": None,
                "end_iso": None,
                "category": "obituary",
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


# Order matters: the first pattern that matches wins, so put more
# specific phrases ahead of general ones (e.g. "estate sale" is checked
# before the bare word "sale" would ever get a chance to).
EVENT_TYPE_KEYWORDS = [
    (re.compile(r"\b(city council|county commission|school board|meeting)\b", re.IGNORECASE), "Meeting"),
    (re.compile(r"\b(fundraiser|benefit dinner|benefit\b|donation drive|coalition drive|blood drive)\b", re.IGNORECASE), "Fundraiser / Benefit"),
    (re.compile(r"\b(garage sale|yard sale|rummage sale)\b", re.IGNORECASE), "Garage Sale"),
    (re.compile(r"\b(auction|estate sale|liquidation)\b", re.IGNORECASE), "Auction / Estate Sale"),
    (re.compile(r"\b(festival|\bfair\b|parade|derby|homecoming|railroad days|trapshoot|celebration)\b", re.IGNORECASE), "Festival / Fair"),
    (re.compile(r"\b(church|revival|vbs|bible study|worship)\b", re.IGNORECASE), "Religious / Church"),
    (re.compile(r"\bchamber\b", re.IGNORECASE), "Business / Chamber"),
    (re.compile(r"\b(concert|theater|theatre|art show|craft fair|open mic)\b", re.IGNORECASE), "Arts & Entertainment"),
    (re.compile(r"\b(courthouse closed|election|public notice|road closure|closed\b)\b", re.IGNORECASE), "Government Notice"),
]


def guess_event_type(ev):
    """Best-effort event-type tag for calendar-view.html's type filter and
    manage-events.html's admin view. A manually-submitted event already
    carries a submitter-picked type (see load_manual_events()); this only
    fills in a guess for everything else, which is most of the calendar,
    since it's almost entirely auto-scraped and has no such field. Falls
    back to the existing sports/obituary category (already reliable,
    since those come from dedicated sources rather than a keyword guess)
    and finally to "Other" rather than leaving anything untagged."""
    if ev.get("event_type"):
        return ev["event_type"]
    if ev.get("category") == "sports":
        return "Sports"
    if ev.get("category") == "obituary":
        return "Obituary / Visitation"
    name = ev.get("name") or ""
    for pattern, event_type in EVENT_TYPE_KEYWORDS:
        if pattern.search(name):
            return event_type
    return "Other"


def build_calendar(events, calname=None):
    cal = Calendar()
    cal.add("prodid", f"-//{CONFIG['county_display_name']} Events Scraper//{CONFIG['uid_domain']}//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", calname or CONFIG["calendar_title"])
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
        if ev.get("category"):
            # Lets calendar-view.html's own filter recognize category
            # (currently just "sports") straight from a normal
            # linn_county_events.ics fetch, without needing the separate
            # "-no-sports.ics" files write_town_ics_files()/main() write
            # for actual phone/computer calendar subscriptions.
            event.add("categories", ev["category"])
        if ev.get("event_type"):
            # A custom X-property (RFC 5545 allows these; real calendar
            # apps just ignore properties they don't recognize) -- this is
            # only for calendar-view.html's own type filter/label, see
            # guess_event_type() for how every event gets one.
            event.add("x-event-type", ev["event_type"])

        cal.add_component(event)

    return cal


def _write_category_variant_ics_files(events, base_path, calname_base):
    """Write one .ics per non-empty combination of FILTERABLE_CATEGORIES
    to exclude (e.g. "{base_path}-no-sports.ics",
    "{base_path}-no-sports-no-obituary.ics", ...) alongside the
    "everything included" file the caller already writes at
    "{base_path}.ics" -- so a subscriber can check exactly the kinds of
    events they want on index.html instead of an all-or-nothing
    subscription. Shared by main() (the county-wide file) and
    write_town_ics_files() (each per-town file) so the combination logic
    -- and the naming scheme calendar-view.html/index.html need to match
    -- only lives in one place."""
    for r in range(1, len(FILTERABLE_CATEGORIES) + 1):
        for excluded in itertools.combinations(FILTERABLE_CATEGORIES, r):
            suffix = "".join(f"-no-{c}" for c in excluded)
            calname = f"{calname_base} (" + ", ".join(f"No {c.title()}" for c in excluded) + ")"
            filtered = [ev for ev in events if ev.get("category") not in excluded]
            calendar = build_calendar(filtered, calname=calname)
            with open(f"{base_path}{suffix}.ics", "wb") as f:
                f.write(calendar.to_ical())


def write_town_ics_files(events):
    """One filtered .ics per town in docs/towns/, so someone can subscribe
    their phone/computer calendar to just their own town's events instead
    of always getting the whole county's -- the calendar-app equivalent
    of the town filter already in calendar-view.html and the per-town
    email filtering already in send_reminders.py. Events with no
    resolvable town (a bare "Marceline, MO"-only match is fine; blank/
    unparseable locations are not) are simply omitted from every town
    file rather than guessed at.

    Also writes every FILTERABLE_CATEGORIES exclusion combination per
    town via _write_category_variant_ics_files() -- e.g.
    docs/towns/brookfield-no-sports.ics -- the same idea as main() does
    for the county-wide file, just per-town."""
    os.makedirs(TOWN_ICS_DIR, exist_ok=True)
    for town in CONFIG["towns"]:
        town_events = [ev for ev in events if extract_town(ev.get("location", ""), CONFIG) == town]
        calname_base = f"{town} Events ({CONFIG['calendar_title']})"
        calendar = build_calendar(town_events, calname=calname_base)
        slug = re.sub(r"[^a-z0-9]+", "-", town.lower()).strip("-")
        base_path = os.path.join(TOWN_ICS_DIR, slug)
        with open(f"{base_path}.ics", "wb") as f:
            f.write(calendar.to_ical())

        _write_category_variant_ics_files(town_events, base_path, calname_base)


def send_mass_failure_alert(new_count, previous_count, source_health):
    """Emails the admin when a run is about to be aborted for losing most
    of its sources at once (see the guard in main()) -- a failed GitHub
    Actions run alone is easy to miss, and this is the one failure mode
    where staying silent means the live calendar goes stale for everyone
    subscribed to it.
    """
    if not BREVO_API_KEY:
        print("  BREVO_API_KEY isn't set -- skipping mass-failure alert email.", file=sys.stderr)
        return

    failed = [s for s in source_health if not s["ok"]]
    lines = [
        f"Today's scrape of the {CONFIG['county_display_name']} calendar found only "
        f"{new_count} events, down from {previous_count} in the last published "
        "calendar. That's more than a 50% drop, which almost always means "
        "several sources failed at once rather than that events actually "
        "disappeared -- so this run was NOT published. The site is still "
        "showing the last good calendar.",
        "",
    ]
    if failed:
        lines.append("Sources that failed this run:")
        for s in failed:
            lines.append(f"- {s['name']}: {s['error']}")
    else:
        lines.append(
            "No individual source reported an error -- check the full run log "
            "in the Actions tab for what changed."
        )
    lines.append("")
    lines.append("Nothing to do unless this keeps happening on the next run too.")
    body = "\n".join(lines)

    try:
        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
            json={
                "sender": {"email": CONFIG["sender_email"], "name": CONFIG["sender_name"]},
                "to": [{"email": CONFIG["admin_email"]}],
                "subject": f"Scrape aborted -- {CONFIG['county_display_name']} calendar lost most of its sources",
                "textContent": body,
            },
            timeout=30,
        )
        resp.raise_for_status()
        print("  Sent mass-failure alert email.")
    except requests.RequestException as e:
        print(f"  WARNING: failed to send mass-failure alert: {e}", file=sys.stderr)


def main():
    # Per-source health, written to docs/source_status.json alongside the
    # .ics at the end of this run -- see docs/status.html. Sources whose
    # own function already catches its errors internally and degrades to
    # an empty list (Brookfield city, MSHSAA schools, the newspaper page,
    # county government) can't be distinguished here between "genuinely
    # nothing new" and "the fetch silently failed" -- those are recorded
    # with ok=True regardless, since fixing that fully means changing
    # every source function's return signature. The sources that already
    # propagate real exceptions to this function (CitySpark, Rhodes, the
    # Tribute Technology funeral homes) get an accurate ok/error status.
    source_health = []

    def record_health(name, count, error=None):
        source_health.append({"name": name, "count": count, "ok": error is None, "error": error})

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

        # get_list_html() already retries its own transient failures (see
        # its docstring); this catches the case where all retries were
        # exhausted, so a dead CitySpark widget doesn't take down the
        # other eight working sources with it -- the same reasoning as
        # the Rhodes/funeral-home try/excepts below, just applied to the
        # source that used to be allowed to crash the whole run.
        try:
            html = get_list_html(page)
            events = parse_events(html)
            fill_descriptions(page, events)
            record_health("CitySpark (Linn County Leader)", len(events))
        except Exception as e:
            print(f"  WARNING: couldn't fetch CitySpark's widget: {e}", file=sys.stderr)
            events = []
            record_health("CitySpark (Linn County Leader)", 0, error=str(e))

        # Rhodes' site appears to challenge/block traffic from GitHub
        # Actions' well-known CI IP ranges even though the same request
        # works fine from a residential IP -- a real, observed failure
        # in production, not a hypothetical. A failure here must not
        # take down the other six working sources, so it's caught and
        # logged rather than left to propagate and crash the whole run.
        try:
            rhodes_html = get_rhodes_obituaries_html(page)
            rhodes_events = parse_rhodes_obituaries(rhodes_html)
            record_health("Rhodes Funeral Home", len(rhodes_events))
        except Exception as e:
            print(f"  WARNING: couldn't fetch Rhodes Funeral Home's obituaries: {e}", file=sys.stderr)
            rhodes_events = []
            record_health("Rhodes Funeral Home", 0, error=str(e))

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
    record_health("City of Brookfield calendar", len(brookfield_events))
    if brookfield_events:
        print(f"Including {len(brookfield_events)} event(s) from the City of Brookfield's calendar\n")
        events.extend(brookfield_events)

    for school in MSHSAA_SCHOOLS:
        school_events = get_mshsaa_school_events(**school)
        record_health(f"{school['district']} (MSHSAA)", len(school_events))
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
        # meaningful signal that two events are the same one. "Obituary"
        # prefixes every single obituary entry's name, so it's a
        # guaranteed false-positive contributor between any two
        # same-day obituaries -- caught this for real during testing
        # ("Letty Jean Parr" wrongly matched "Bonnie Jean Alexander" via
        # shared "obituary" + "jean").
        "linn", "county", "community", "annual", "obituary",
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

    leader_editorial_events = get_leader_editorial_calendar_events()
    record_health("Newspaper's Community Calendar page", len(leader_editorial_events))
    add_with_dedup(leader_editorial_events, "the newspaper's manual calendar page")

    chamber_events = get_brookfield_chamber_events()
    record_health("Brookfield Area Chamber of Commerce", len(chamber_events))
    add_with_dedup(chamber_events, "the Brookfield Area Chamber of Commerce's calendar")

    county_gov_events = get_linn_county_government_events()
    record_health("Linn County government calendar", len(county_gov_events))
    add_with_dedup(county_gov_events, "Linn County government's calendar")

    marceline_events = get_downtown_marceline_events()
    record_health("Downtown Marceline Foundation", len(marceline_events))
    add_with_dedup(marceline_events, "the Downtown Marceline Foundation's calendar")

    # The most fragile source in this file (see get_teter_auction_events()'s
    # docstring) -- a real parsing failure here shouldn't take down the
    # other eleven working sources with it.
    try:
        teter_events = get_teter_auction_events()
        record_health("Teter Auction Company", len(teter_events))
    except Exception as e:
        print(f"  WARNING: couldn't parse Teter Auction Company's homepage: {e}", file=sys.stderr)
        teter_events = []
        record_health("Teter Auction Company", 0, error=str(e))
    add_with_dedup(teter_events, "Teter Auction Company's upcoming auctions")

    add_with_dedup(rhodes_events, "Rhodes Funeral Home (in-county obituaries)")

    for home in TRIBUTE_TECHNOLOGY_FUNERAL_HOMES:
        try:
            home_events = get_tribute_technology_obituaries(**home)
            record_health(home["name"], len(home_events))
        except Exception as e:
            print(f"  WARNING: couldn't fetch {home['name']}'s obituaries: {e}", file=sys.stderr)
            home_events = []
            record_health(home["name"], 0, error=str(e))
        add_with_dedup(home_events, f"{home['name']} (in-county obituaries)")

    manual_events = load_manual_events()
    if manual_events:
        print(f"Including {len(manual_events)} approved community-submitted event(s)\n")
        events.extend(manual_events)

    for ev in events:
        ev["event_type"] = guess_event_type(ev)

    if not events:
        print("No events found -- the page structure may have changed.")
        sys.exit(1)

    # A single run rarely loses more than a handful of sources -- if most of
    # them failed at once (a flaky runner, a network blip, a widespread
    # timeout) the previous commit is almost certainly more accurate than
    # this run's partial results. Bail out here rather than letting main()
    # overwrite -- and the "Commit updated calendar file" workflow step
    # publish -- a near-empty calendar over a healthy one. See the incident
    # on 2026-08-22 where a run with 6 failing sources still committed and
    # dropped the live feed from 761 events to 37.
    if os.path.exists(ICS_PATH):
        with open(ICS_PATH, encoding="utf-8") as f:
            previous_count = f.read().count("BEGIN:VEVENT")
        if previous_count >= 20 and len(events) < previous_count * 0.5:
            print(
                f"ABORTING: found only {len(events)} events this run, down from "
                f"{previous_count} in the last published calendar (more than a "
                "50% drop). This usually means several sources failed at once "
                "rather than that events actually disappeared -- check the "
                "WARNINGs above. Leaving the previously published calendar in "
                "place instead of overwriting it.",
                file=sys.stderr,
            )
            send_mass_failure_alert(len(events), previous_count, source_health)
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

    _write_category_variant_ics_files(events, ICS_PATH.removesuffix(".ics"), CONFIG["calendar_title"])

    write_town_ics_files(events)
    print(f"Wrote per-town .ics files to {TOWN_ICS_DIR}/\n")

    with open(SOURCE_STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {"generated_at": datetime.now(timezone.utc).isoformat(), "sources": source_health},
            f,
            indent=2,
        )

    print(f"Wrote {ICS_PATH}\n")
    print(f"----- {ICS_PATH} contents -----")
    print(ics_bytes.decode("utf-8"))


if __name__ == "__main__":
    main()
