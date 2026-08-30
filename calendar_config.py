#!/usr/bin/env python3
"""
Loads docs/config.json -- the single source of truth for everything that
differs between deployments of this system (domain, towns, timezone,
third-party account IDs, sender identity). Shared by every Python script
so a new customer/instance only requires editing that one file, not
hunting through each script.

The HTML pages under docs/ read the same file directly via fetch(), so
Python and JS never have two copies of these values to keep in sync.
"""
import json
import os
import re

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "config.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_town(location, config):
    """LOCATION strings look like "Venue Name | Town, ST" or just
    "Town, ST" -- take the last "|"-separated segment (the actual
    address part) and pull the town out of that, so a venue name that
    happens to contain another town's name (e.g. "St Joseph Christian
    School... | Marceline, MO") doesn't get misread. Shared by
    send_reminders.py (per-town email filtering) and
    scrape_linn_county_calendar.py (per-town .ics files) so both stay
    in sync with the same logic -- docs/calendar-view.html's
    extractTown() is a JS mirror of this for the web view's town filter.

    Returns whatever place name it can read out of LOCATION -- which
    might not be one of config['towns'] at all (a game played in a
    neighboring town, an unincorporated place like Hurricane Branch, a
    lake) -- see town_or_other() below for the filter/subscription-bucket
    version of this that collapses those into "Other"."""
    if not location:
        return None
    last_segment = location.split("|")[-1].strip()
    m = re.search(rf"([A-Za-z .]+?),\s*{re.escape(config['state'])}\b", last_segment)
    return m.group(1).strip() if m else None


def town_or_other(location, config):
    """The bucket a "town" filter/subscription choice should use: one of
    config['towns'], or "Other" for anything that isn't -- an event with
    no resolvable location, one outside the county's 8 incorporated
    towns, or at a place like a lake or unincorporated community. As a
    rule, every event should fall into exactly one of these buckets
    rather than silently vanishing from every town-based view the way a
    bare None from extract_town() would."""
    town = extract_town(location, config)
    return town if town in config["towns"] else "Other"
