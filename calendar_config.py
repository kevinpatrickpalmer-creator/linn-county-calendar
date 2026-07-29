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

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "config.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
