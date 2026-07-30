# Linn County Leader — Community Calendar Scraper

Scrapes events from multiple Linn County sources and publishes the combined
results as an `.ics` calendar feed at `docs/linn_county_events.ics`:

- [linncountyleader.com/calendar](https://www.linncountyleader.com/calendar/)
  — a client-side rendered CitySpark widget, so this uses Playwright to
  render it before parsing with BeautifulSoup. In practice this source is
  almost entirely Marceline-based (the newspaper that runs it is
  Marceline-based and only onboarded contacts it already had).
- [brookfieldcity.com/calendar](https://brookfieldcity.com/calendar/) — the
  City of Brookfield's own calendar, added because Brookfield (the county's
  largest town) had zero presence in CitySpark despite having real,
  actively-maintained event data of its own. Plain HTML + an XML sitemap,
  no headless browser needed.
- School districts' game schedules, via [MSHSAA](https://www.mshsaa.org/)
  — district sites often don't host their own schedules; MSHSAA hosts a
  shared calendar for every Missouri high school by school ID instead.
  Plain legacy ASP.NET HTML, no headless browser needed. `MSHSAA_SCHOOLS`
  in `scrape_linn_county_calendar.py` currently covers Brookfield R-III
  (zero CitySpark presence) and Marceline R-V (CitySpark had only 9 of
  its 135 real upcoming events) — `get_mshsaa_school_events()` is fully
  generic, so adding another Missouri school is just one more entry in
  that list. CitySpark's own school-district-tagged events are filtered
  out in `main()` so the same game doesn't appear twice.
- The newspaper's hand-typed ["Community Calendar"](https://www.linncountyleader.com/community-calendar-205/)
  page — a separate WordPress post from the CitySpark widget, where staff
  type up emailed submissions as prose under date headers rather than
  structured fields. Covers some real towns/groups with no other online
  presence at all (e.g. Laclede Pershing Days). Plain HTML, no headless
  browser needed — see `get_leader_editorial_calendar_events()` for how
  the lack of structured fields is handled. A same-date + shared-keyword
  check drops entries that just duplicate something already captured
  more cleanly by another source.
- [Linn County government's own calendar](https://linncomo.com/calendar-of-events/)
  — embedded on the county's site as a *public* Google Calendar iframe,
  which means no HTML scraping at all: Google publishes a standard ICS
  export for any public calendar, so `get_linn_county_government_events()`
  just fetches and parses it with the same `icalendar` library used
  elsewhere. Low volume (courthouse hours, elections, tax sale) but the
  only source covering Linneus, the county seat, which has no presence
  anywhere else in this system. Also run through the same dedup check
  as the newspaper's page, since e.g. its "PRIMARY ELECTION" would
  otherwise double up with that page's own "Primary Election" entry.
- [Rhodes Funeral Home's obituaries](https://www.rhodesfh.com/obituaries/)
  (Brookfield) — recent death notices, the one source here that isn't
  upcoming events. Dated by date of death/posting rather than the
  funeral service date, which is sometimes in the obituary text but too
  unreliable and consequential to extract by guessing. Rhodes serves
  families well beyond Linn County, so entries are filtered to a
  conservative "of &lt;Linn County town&gt;" match near the start of the
  bio text — an ambiguous case is excluded rather than risked. Only the
  last `RHODES_RECENCY_DAYS` days are included. JS-rendered like
  CitySpark, but individual obituary pages sit behind a Cloudflare bot
  challenge, so everything needed is pulled from the one listing page.

Each source normalizes to the same event shape before merging, so adding
another town's source is a matter of writing one more `get_*_events()`
function in `scrape_linn_county_calendar.py` — see that file's module
docstring for details.

A GitHub Actions workflow (`.github/workflows/update-calendar.yml`) re-runs
the scraper every 4 hours and commits the refreshed file. GitHub Pages
serves `docs/` as a static site, reachable at
[linncounty.communitycalendarconnect.com](https://linncounty.communitycalendarconnect.com/)
(a custom domain -- part of a multi-community "Community Calendar Connect"
setup, one subdomain per town/county, all pointing at their own repo). The
`.ics` file there is a stable URL suitable for subscribing to from a phone
calendar app.

## Configuration (`docs/config.json`)

Everything that differs between deployments of this system — display name,
domain, timezone, state abbreviation, the town list, third-party account
IDs (Web3Forms key, Google Form entry IDs, subscriber sheet CSV URL), the
GitHub repo/branch, and the sender/admin email addresses — lives in one
file: `docs/config.json`. Nothing else in the codebase should need
Linn-County-specific values hardcoded into it.

- **Python scripts** load it via `calendar_config.load_config()`.
- **HTML pages** (`index.html`, `submit.html`, `admin.html`,
  `manage-events.html`, `calendar-view.html`) fetch it client-side with
  `fetch("config.json")` before rendering anything that depends on it
  (town dropdowns, page titles, links back to GitHub, etc.).

To stand up a new instance for another town or county: copy this repo,
edit `docs/config.json`, set up that community's own Web3Forms account /
Google Form / Brevo sender, add the `BREVO_API_KEY` secret, point GitHub
Pages at their subdomain, and write or adapt a scraper for their local
news/events source if it isn't the same CitySpark widget
`scrape_linn_county_calendar.py` targets — `CALENDAR_URL` there is
deliberately left out of `config.json` since it's specific to the source
site, not the deployment.

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
- **Editing or cancelling** an approved event: `docs/manage-events.html`
  lists every current manual event (pulled live from GitHub) with direct
  Edit / Cancel links straight to GitHub's file editor and delete-confirm
  pages. Scraped events aren't listed -- those aren't ours to change, and
  track the newspaper's own site automatically.

## Viewing the calendar online

`docs/calendar-view.html` is a visual month-grid calendar (parses
`linn_county_events.ics` client-side, no backend) meant for people looking
at events in a browser rather than subscribing on a phone. It's also built
to be embedded on other sites (town/school pages, etc.) via a plain
`<iframe>` -- the page itself has a "Embed this calendar" snippet, and is
responsive down to narrow sidebar-widget widths.

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
