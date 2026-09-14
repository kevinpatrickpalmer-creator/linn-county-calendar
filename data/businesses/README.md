# Business & organization directory listings

Each `.json` file in this directory is one **approved** listing in the
public directory (`docs/directory.html`), created via
[`docs/admin-business.html`](../../docs/admin-business.html) after
reviewing a submission from
[`docs/submit-business.html`](../../docs/submit-business.html).

`build_business_directory.py` reads every file here and writes the
combined result to `docs/businesses.json`, which `docs/directory.html`
fetches directly — there's no scraping involved, unlike the events
calendar.

Rejected or still-pending submissions never get a file here — same as
`data/manual_events/`, there's no "is this approved?" flag to check, so
there's no way for an unreviewed submission to leak into the public
directory.

Expected shape of each file:

```json
{
  "name": "Knott's Tree Service",
  "category": "Home & Trade Services",
  "town": "Marceline",
  "address": "123 Main St, Marceline, MO",
  "phone": "(660) 555-0142",
  "website": "https://knottstreeservice.com",
  "email": "info@knottstreeservice.com",
  "hours": "Mon-Fri 8am-5pm",
  "description": "Tree removal, trimming, and stump grinding."
}
```

Only `name` and `town` are required — everything else may be omitted or
left blank. `category` should match one of `business_categories` in
`docs/config.json` when possible (it's what the directory's filter uses),
but a listing with an unrecognized or missing category still shows up
under "Other".

## Home service listings (`scrape_home_services.py`)

Files whose `"source"` field is `"google_maps"` were added automatically
by `scrape_home_services.py` (pulled from Google Maps via
[Outscraper](https://outscraper.com), see that script's module docstring)
rather than through the submit/approve flow above — these publish with no
human review, unlike everything else in this directory. `source` and the
scraper's own `place_id` field are bookkeeping only:
`build_business_directory.py` only copies a fixed field whitelist into
the public `docs/businesses.json`, so neither ever reaches the site
itself.

The scraper never overwrites a file that already exists (matched by the
same `<town>-<name>` slug `docs/admin-business.html` uses) — a listing
someone hand-edited, whether originally scraped or manually approved,
always wins over a re-scrape.
