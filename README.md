# Linn County Leader — Community Calendar Scraper

Scrapes the community events widget on [linncountyleader.com/calendar](https://www.linncountyleader.com/calendar/)
(a client-side rendered CitySpark widget, so this uses Playwright to render
it before parsing with BeautifulSoup) and publishes the results as an `.ics`
calendar feed at `docs/linn_county_events.ics`.

A GitHub Actions workflow (`.github/workflows/update-calendar.yml`) re-runs
the scraper every 4 hours and commits the refreshed file. GitHub Pages
serves `docs/` as a static site, so the `.ics` file is reachable at a
stable URL suitable for subscribing to from a phone calendar app.

## Run locally

```bash
pip install -r requirements.txt
playwright install chromium
python scrape_linn_county_calendar.py
```

Writes/overwrites `docs/linn_county_events.ics`.
