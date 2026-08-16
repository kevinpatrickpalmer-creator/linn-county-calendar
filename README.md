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
  in `scrape_linn_county_calendar.py` covers 5 of the county's 8 towns
  directly: Brookfield R-III, Marceline R-V, Bucklin R-II, Linn County
  R-I (physically in Purdin, also serves Linneus and Browning), and
  Meadville R-IV — `get_mshsaa_school_events()` is fully generic, so
  adding another Missouri school is just one more entry in that list.
  (Laclede appears to have no school of its own left; no MSHSAA-listed
  successor was found.) CitySpark's own school-district-tagged events
  are filtered out in `main()` so the same game doesn't appear twice.
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
- [Rhodes](https://www.rhodesfh.com/obituaries/),
  [Wright](https://www.wright-funeralhome.com/), and
  [Delaney](https://www.delaneyfuneralhome.com/) Funeral Homes'
  obituaries (Brookfield, Brookfield, and Marceline/Bucklin
  respectively) — recent death notices, the only sources here that
  aren't upcoming events. Dated by date of death/posting rather than
  the funeral service date, which is sometimes in the obituary text but
  too unreliable and consequential to extract by guessing. All three
  serve families well beyond Linn County, so entries are filtered to a
  conservative in-county town match — an ambiguous case is excluded
  rather than risked. Only the last `OBITUARY_RECENCY_DAYS` days are
  included. Rhodes is JS-rendered like CitySpark, with individual
  obituary pages behind a Cloudflare bot challenge, so everything
  needed is pulled from the one listing page. Wright and Delaney run
  the same third-party platform and need no headless browser at all —
  a plain XML sitemap plus a schema.org JSON-LD block on each page
  cover everything; `get_tribute_technology_obituaries()` is fully
  generic across any funeral home on that platform.
- The [Brookfield Area Chamber of Commerce](https://brookfieldmochamber.com)'s
  community events calendar — also the shared calendar for Main Street
  Brookfield and the Brookfield Area Growth Partnership (same umbrella
  org, different public-facing names). Runs the same "Events Calendar WD"
  WordPress plugin as the City of Brookfield's own site above, so
  `get_brookfield_chamber_events()` reuses the same schema.org JSON-LD
  approach, just discovered via WordPress's own built-in sitemap rather
  than a dedicated one. Genuinely new content beyond CitySpark and the
  city's own calendar — Railroad Days, the Great Pershing Balloon Derby,
  Main Street Sip & Stroll — run through the same date-and-keyword
  dedup check as the newspaper's page above, since it
  occasionally lists the same event the city or a school district
  already covers. Unlike the city's own calendar, not every event here
  is inside Brookfield itself, so the town is parsed from each event's
  own street address rather than assumed.
- The [Downtown Marceline Foundation](https://www.downtownmarceline.org/events/)'s
  calendar — embedded on their site the same way Linn County government's
  is (a *public* Google Calendar iframe), so `get_downtown_marceline_events()`
  is another plain ICS fetch, no scraping needed. Genuinely new Marceline
  content beyond CitySpark and the newspaper's page — Patriotic Pie War,
  the Spring Festival, Shop Hop, the library's own Quarter Auction
  fundraiser — even though CitySpark is itself Marceline-based, it only
  ever captured a fraction of the town's real event volume (see
  `MSHSAA_SCHOOLS`' comment for the same story with school games). Run
  through the same dedup check as the newspaper's page, since its own
  "Wine & Art Stroll" would otherwise double up with CitySpark's entry
  for the same event.
- [Teter Auction Company](https://www.teterauction.com/)'s upcoming
  auctions — physically headquartered in Laclede, and its homepage lists
  real land/estate auctions across the region. The only auction/estate
  -sale source found with both real in-county content and something
  worth scraping (Sayre, Smith, Scotty's, McCurdy, and Enyeart were all
  checked; none had both, and a national estate-sale aggregator had zero
  listings anywhere near Linn County). Unlike every other source here,
  there's no structured markup at all — `get_teter_auction_events()`
  parses the page's own rendered text, the same spirit as
  `get_leader_editorial_calendar_events()`, and is the most fragile
  source in this file: a homepage redesign could break it silently. Also
  widens its town match to include Macon and Chillicothe (both along the
  same Highway 36 corridor) since auctions draw people well beyond their
  own town in a way most other events here don't — those still land in
  the whole-county calendar without appearing in any single Linn County
  town's own filtered `.ics`, since `extract_town()` has no fixed town
  list of its own.

Each source normalizes to the same event shape before merging, so adding
another town's source is a matter of writing one more `get_*_events()`
function in `scrape_linn_county_calendar.py` — see that file's module
docstring for details.

## Source health

Every run writes `docs/source_status.json` alongside the `.ics` file --
per-source event counts and, for the sources that propagate real errors
back to `main()` (CitySpark, Rhodes, Wright, Delaney, Teter Auction
Company), whether that run succeeded. `docs/status.html` (an admin-only
page, not linked from the
public site, same as `admin.html`/`manage-events.html`) renders this so a
persistent failure like Rhodes' Cloudflare block is visible at a glance
instead of only showing up by chance in GitHub Actions logs. Sources that
catch their own errors internally (Brookfield city, the Brookfield
Chamber, MSHSAA schools, the newspaper page, county government, the
Downtown Marceline Foundation) always show as OK here even if their
count unexpectedly drops to zero -- a sudden 0 from a normally-active
source is still worth checking by hand.

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
- **New-event digest:** `notify_new_scraped_events.py` (also run each
  scheduled workflow, right after the manual-event confirmations) emails
  the admin a single summary -- count plus a sorted list, capped at 40 with
  a "+N more" note -- of any *scraped* events that are newly present since
  the last run. This is a "the scrapers are actually finding new stuff"
  heartbeat, not a per-event announcement like the manual one above (which
  is why manually-approved events are excluded here -- they already get
  their own confirmation and don't need a second one). A run that finds
  nothing new sends no email at all.
- **Recurring events:** both `submit.html` and `admin.html` have a
  "Repeats?" field (weekly, every 2 weeks, monthly on the same week & day
  -- e.g. the 3rd Monday -- or monthly on the same date) plus a required
  end date, for things like a political party's or club's standing
  monthly meeting that would otherwise need resubmitting by hand forever.
  One JSON file still covers the whole series (just with `recurrence` and
  `repeat_until` fields added) -- `_expand_manual_event_dates()` in
  `scrape_linn_county_calendar.py` is what turns that into one concrete
  calendar entry per occurrence at scrape time, computed with
  `python-dateutil` rather than by approximating "~30 days later" (which
  would drift onto the wrong week for a "3rd Monday" pattern).
- **Rejecting** a submission means simply not creating a file for it —
  pending/rejected submissions never touch `data/manual_events/` or the
  public `.ics`.
- **Editing or cancelling** an approved event: `docs/manage-events.html`
  lists every current manual event (pulled live from GitHub), showing a
  "Repeats... until ..." line for recurring ones, with direct Edit /
  Cancel links straight to GitHub's file editor and delete-confirm pages
  -- cancelling a recurring event's one file removes every future
  occurrence at once. Scraped events aren't listed -- those aren't ours
  to change, and track the newspaper's own site automatically.

## Viewing the calendar online

`docs/calendar-view.html` is a visual month-grid calendar (parses
`linn_county_events.ics` client-side, no backend) meant for people looking
at events in a browser rather than subscribing on a phone. It's also built
to be embedded on other sites (town/school pages, etc.) via a plain
`<iframe>` -- the page itself has a "Embed this calendar" snippet, and is
responsive down to narrow sidebar-widget widths.

## Printable flyer

`docs/flyer.html` is a one-page, letter-sized flyer for recruiting
businesses/institutions/organizations to submit their events -- linked
from the bottom of `index.html` ("Printable flyer for businesses &
organizations") so it's always somewhere the community can find and print
it, not just a link handed out once. Has a "Print this flyer" button and
print-specific CSS (`@media print`) sized to fit one printed page.

Pulls from `config.json` the same way every other page does (calendar
name, town list, domain, admin email), so it stays correct if this ever
gets reused for another town/county -- the only genuinely Linn-County
-specific content is the Missouri-with-Linn-County-highlighted map in the
masthead (public domain, from [Wikimedia Commons](https://en.wikipedia.org/wiki/File:Map_of_Missouri_highlighting_Linn_County.svg),
recolored to match the site's palette) and the copy itself, both of which
would need swapping for a different deployment same as `CALENDAR_URL` in
the scraper.

Has two QR codes, generated client-side with `docs/qrcode.js`
([kazuhikoarase/qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator),
MIT licensed) -- the same script `index.html`'s own QR code
(next to "Submit a community event") uses, so all three point at
consistent URLs:
- **Scan to submit** -- `submit.html`, for the business/organization
  actually adding their event.
- **Scan to subscribe** -- the countywide `webcal://` link directly
  (not just the website), so a resident gets the whole calendar in one
  scan with no extra taps. It can't offer per-town or category
  filtering the way the button on `index.html` can, since a QR code is
  a fixed link -- that's the deliberate tradeoff for a flyer, where
  low friction for a casual scanner matters more than granularity.

## Landing page, reminders & app interest list

- **Landing page:** `docs/index.html` — the "Subscribe to Calendar" button
  and a preferences form (email + two independent opt-in checkboxes). A
  "Which events?" dropdown lets someone subscribe their phone/computer
  calendar to just one town instead of the whole county, pointing at
  `docs/towns/<slug>.ics` instead of the full `linn_county_events.ics` --
  see `write_town_ics_files()` in `scrape_linn_county_calendar.py`. This
  is the calendar-subscription equivalent of the town filter already in
  `calendar-view.html` and the per-town email filtering below; all three
  now share the same `extract_town()` from `calendar_config.py`.
- **Category checkboxes:** also on `docs/index.html`, "School sports
  games" and "Obituaries" (both checked by default) let someone exclude
  a category they don't want mixed into their subscription -- e.g.
  Marceline's events minus school sports games. Each event optionally
  carries a `category` (only `get_mshsaa_school_events()` tags `"sports"`
  and the three funeral home sources tag `"obituary"` -- these are the
  only sources reliable enough to tag by source rather than by guessing
  at event names). `_write_category_variant_ics_files()` in
  `scrape_linn_county_calendar.py` writes every combination of these to
  exclude, both for the county-wide file
  (`linn_county_events-no-sports.ics`, etc.) and per-town
  (`docs/towns/<slug>-no-sports.ics`, etc.) -- `FILTERABLE_CATEGORIES`
  there is the single source of truth both the Python file-naming and
  index.html's JS combine to match. `calendar-view.html` also reads each
  event's `CATEGORIES` field directly (added in `build_calendar()`) for
  its own "Hide sports"/"Hide obituaries" checkboxes, filtering
  client-side rather than needing a separate file per combination.
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
- **Community App interest** ("Notify me when the Community App launches")
  reuses the same `newsletter` field/column (both in the HTML element IDs
  and `config.json`'s `entry_newsletter` Google Form field) -- it was
  originally a newsletter opt-in, repurposed to gauge interest in a future
  app instead of adding a separate opt-in and Form field for the same
  "email us later" purpose. Nothing sends to this list yet; it's just
  collecting interest.

## Run locally

```bash
pip install -r requirements.txt
playwright install chromium
python scrape_linn_county_calendar.py
```

Writes/overwrites `docs/linn_county_events.ics`, merging in anything found
under `data/manual_events/`.

To test the reminder script locally: `BREVO_API_KEY=... python send_reminders.py`
