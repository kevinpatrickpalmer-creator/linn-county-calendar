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

The scraper never overwrites a file that already exists, matched by
either its `<town>-<name>` slug (same convention `docs/admin-business.html`
uses) or its `place_id` — a listing someone hand-edited, whether
originally scraped or manually approved, always wins over a re-scrape.
Matching on `place_id` too (not just the slug) matters because a
service-area business (a truck, no storefront) often comes back from
Google with no city at all and lands under "Other" -- if you find its
real town elsewhere (its own website, say) and correct the file by hand,
the slug that correction implies no longer matches what the scraper
would compute for that same business next time (still no city, still
"Other" in Google's own data), so matching by `place_id` as well is what
actually stops it from being silently re-added as a duplicate under its
old "Other" slug on the next run. When you hand-correct a listing like
this, it's worth setting `"source"` to something other than
`"google_maps"` (e.g. `"google_maps_corrected"`) so it's visibly not what
the scraper originally wrote — cosmetic only, `build_business_directory.py`
doesn't look at the value.
