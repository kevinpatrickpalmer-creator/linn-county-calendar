# Linn County Leader — Community Calendar Scraper

Scrapes the community events widget on [linncountyleader.com/calendar](https://www.linncountyleader.com/calendar/)
(a client-side rendered CitySpark widget, so this uses Playwright to render
it before parsing with BeautifulSoup) and publishes the results as an `.ics`
calendar feed at `docs/linn_county_events.ics`.

A GitHub Actions workflow (`.github/workflows/update-calendar.yml`) re-runs
the scraper every 4 hours and commits the refreshed file. GitHub Pages
serves `docs/` as a static site, reachable at
[linncounty.communitycalendarconnect.com](https://linncounty.communitycalendarconnect.com/)
(a custom domain -- part of a multi-community "Community Calendar Connect"
setup, one subdomain per town/county, all pointing at their own repo). The
`.ics` file there is a stable URL suitable for subscribing to from a phone
calendar app.

## Community event submissions

- **Public submission form:** `docs/submit.html` — no login required, posts
  to [Web3Forms](https://web3forms.com) which emails every submission for
  review. This is the URL to put on flyers / QR codes / links elsewhere.
  Collects a required **Town** (one of the 8 real Linn County towns) plus
  an optional venue, which get combined into the same "Venue | Town, MO"
  shape scraped events use, so town-based reminder filtering works the
  same way regardless of where an event came from.
- **Admin approval helper:** `docs/admin.html` — the submission email
  includes a one-click "review & approve" link that lands here with every
  field already filled in (no retyping). Review it, click "Prepare for
  GitHub", then **Commit new file** on the page GitHub opens. That commit
  is the entire approval step.
- **Approved events:** live as one JSON file per event under
  `data/manual_events/` (see the README in that folder). The scraper merges
  them into every `.ics` regeneration automatically, and
  `notify_new_manual_events.py` (run as part of the same scheduled workflow)
  emails the admin a confirmation for each one that's newly appeared since
  the last run.
- **Rejecting** a submission means simply not creating a file for it —
  pending/rejected submissions never touch `data/manual_events/` or the
  public `.ics`.

## Landing page, reminders & newsletter list

- **Landing page:** `docs/index.html` — the "Subscribe to Calendar" button
  and a preferences form (email + two independent opt-in checkboxes).
- **Storage:** the preferences form posts directly to a Google Form, whose
  linked Google Sheet is published to the web as CSV. Each opt-in is its
  own column, so a single email can have either, both, or neither checked.
  Resubmitting the form (e.g. with both boxes unchecked) overrides the
  previous submission for that email — that's how someone unsubscribes.
- **Daily reminders:** `.github/workflows/daily-reminders.yml` runs
  `send_reminders.py` once a day. It reads `docs/linn_county_events.ics`
  for anything happening tomorrow, reads the subscriber CSV, and emails
  everyone with the reminder box checked via Brevo (verified single
  sender, no custom domain required). SendGrid was the original plan but
  hit an unresolvable account-provisioning bug on their end (see git log).
- **Newsletter opt-ins** are stored in the same sheet but nothing sends to
  them yet — that column is just sitting there ready for whenever an
  actual newsletter gets built.

## Run locally

```bash
pip install -r requirements.txt
playwright install chromium
python scrape_linn_county_calendar.py
```

Writes/overwrites `docs/linn_county_events.ics`, merging in anything found
under `data/manual_events/`.

To test the reminder script locally: `BREVO_API_KEY=... python send_reminders.py`
