#!/usr/bin/env python3
"""
One-off diagnostic: send a single test email via Brevo to confirm a sender
address/domain is working, without touching real subscriber data or
waiting for a real "tomorrow" event. Useful whenever a new sender/domain
is set up (e.g. adding a new community's calendar).

Run:
    BREVO_API_KEY=... TEST_TO=you@example.com TEST_FROM=someone@yourdomain.com python test_brevo_send.py
"""
import os
import sys

import requests

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
TEST_TO = os.environ.get("TEST_TO", "")
TEST_FROM = os.environ.get("TEST_FROM", "")

if not (BREVO_API_KEY and TEST_TO and TEST_FROM):
    print("Set BREVO_API_KEY, TEST_TO, and TEST_FROM environment variables.")
    sys.exit(1)

resp = requests.post(
    "https://api.brevo.com/v3/smtp/email",
    headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
    json={
        "sender": {"email": TEST_FROM, "name": "Community Calendar Connect Test"},
        "to": [{"email": TEST_TO}],
        "subject": "Test send",
        "textContent": f"This is a one-off test send from {TEST_FROM} via Brevo.",
    },
    timeout=30,
)
print(resp.status_code, resp.text)
resp.raise_for_status()
print("Sent successfully.")
