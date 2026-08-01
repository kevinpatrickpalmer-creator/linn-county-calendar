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
    extractTown() is a JS mirror of this for the web view's town filter."""
    if not location:
        return None
    last_segment = location.split("|")[-1].strip()
    m = re.search(rf"([A-Za-z .]+?),\s*{re.escape(config['state'])}\b", last_segment)
    return m.group(1).strip() if m else None
