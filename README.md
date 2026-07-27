# Linn County Leader — Community Calendar Scraper

Scrapes the community events widget on [linncountyleader.com/calendar](https://www.linncountyleader.com/calendar/)
(a client-side rendered CitySpark widget, so this uses Playwright to render
it before parsing with BeautifulSoup) and publishes the results as an `.ics`
calendar feed at `docs/linn_county_events.ics`.

A GitHub Actions workflow (`.github/workflows/update-calendar.yml`) re-runs
the scraper every 4 hours and commits the refreshed file. GitHub Pages
serves `docs/` as a static site, so the `.ics` file is reachable at a
stable URL suitable for subscribing to from a phone calendar app.

## Community event submissions

- **Public submission form:** `docs/submit.html` — no login required, posts
  to [Web3Forms](https://web3forms.com) which emails every submission for
  review. This is the URL to put on flyers / QR codes / links elsewhere.
- **Admin approval helper:** `docs/admin.html` — copy a submission's details
  in here, click through, and commit the pre-filled file GitHub opens for
  you. That's the entire approval step; nothing else is required.
- **Approved events:** live as one JSON file per event under
  `data/manual_events/` (see the README in that folder). The scraper merges
  them into every `.ics` regeneration automatically.
- **Rejecting** a submission means simply not creating a file for it —
  pending/rejected submissions never touch `data/manual_events/` or the
  public `.ics`.

## Run locally

```bash
pip install -r requirements.txt
playwright install chromium
python scrape_linn_county_calendar.py
```

Writes/overwrites `docs/linn_county_events.ics`, merging in anything found
under `data/manual_events/`.
