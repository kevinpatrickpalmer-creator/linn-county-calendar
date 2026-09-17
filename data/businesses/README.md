# Business & organization directory listings

Each `.json` file in this directory is one **approved** listing in the
public directory (`docs/directory.html`). `docs/submit-business.html`
posts to `apps-script/big-ideas.gs`, which commits this file
automatically once a submission is approved (reply "approved" to the
notification email, or edit the sheet directly -- see
`apps-script/README.md`).
[`docs/admin-business.html`](../../docs/admin-business.html) still
works as a manual fallback if that's ever needed instead.

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
  "photo": "https://lh3.googleusercontent.com/...",
  "rating": 4.8,
  "reviews": 23,
  "hours": "Mon-Fri 8am-5pm",
  "description": "Tree removal, trimming, and stump grinding."
}
```

Only `name` and `town` are required — everything else may be omitted or
left blank. `category` should match one of `business_categories` in
`docs/config.json` when possible (it's what the directory's filter uses),
but a listing with an unrecognized or missing category still shows up
under "Other".

`photo`, `rating`, and `reviews` come from Google Maps via
`scrape_businesses.py` -- not every business has all (or any) of these on
Google, and there's no manual-submission equivalent (`submit-business.html`
doesn't collect a photo -- this site has no image upload/hosting
infrastructure), so they're expected to be missing on plenty of
listings, scraped or hand-added alike. `docs/directory.html` renders
whichever of these a listing actually has and simply omits what it
doesn't; nothing here is required for a listing to publish.

`keywords` also comes from Google Maps, but it's search-only --
`docs/directory.html` never displays it, only matches against it. It's
Google's own "subtypes" (a business can be tagged more than one way on
Google even though it only ever gets one `category` here -- Tractor
Supply Co is "Animal feed store, Farm shop, Garden center, Hardware
store, ... Pet store") plus "reviews_tags" (words Google surfaces
because reviewers actually used them, like "farm supplies" or
"workwear"). This is what lets someone searching "clothing" find a farm
store that also carries Carhartt without that store needing a second
visible category.

## Listings scraped from Google Maps (`scrape_businesses.py`)

Files whose `"source"` field is `"google_maps"` were added automatically
by `scrape_businesses.py` (pulled from Google Maps via
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
Google with no city at all and lands under `"town": "Linn County"` -- if
you find its real town elsewhere (its own website, say) and correct the
file by hand, the slug that correction implies no longer matches what
the scraper would compute for that same business next time (still no
city, still the generic fallback in Google's own data), so matching by
`place_id` as well is what actually stops it from being silently
re-added as a duplicate under its old slug on the next run. When you
hand-correct a listing like this, it's worth setting `"source"` to
something other than `"google_maps"` (e.g. `"google_maps_corrected"`) so
it's visibly not what the scraper originally wrote — cosmetic only,
`build_business_directory.py` doesn't look at the value.

**Town, not "Other":** a service-area business Google's own data doesn't
tie to a specific town gets `"town": "Linn County"` rather than "Other"
-- still a real, true label (everything here already passed a 30-mile
distance filter), just not pinned to one of the 8 towns. If you find its
actual town elsewhere (its own website, a BBB/Chamber-of-commerce
listing) editing `"town"` by hand is worth doing when you notice one --
roughly 60% of home-service results come back this way and Google's own
data just doesn't say more. The town doesn't have to be one of the
county's 8 official towns either way; a real nearby place (Chillicothe,
Milan, Bevier, etc.) is what `docs/directory.html`'s town filter is
built from — the point is that whatever it says is true, not that it's
confined to a fixed list. `"town": "Other"` (the literal word) should
never actually appear in a file here; `build_business_directory.py`
holds one back from the public site as a backstop if it ever does.

**Duplicate Google listings:** the same real business sometimes has two
separate Google Maps profiles (different `place_id`, a slightly
different name/address/phone) rather than one, e.g. a stale listing from
before a rebrand. The scraper catches this when a new result's name
(loosely normalized -- see `normalize_business_name()`) and town match
an existing file, and keeps only whichever has more Google reviews,
deleting the other. If you spot a pair it missed (different towns, or
names too different to normalize-match), resolve it the same way by
hand: check each one's review count on Google Maps and delete the
lower-reviewed file.

## Multi-town listings (chains, not coincidentally-shared names)

A business that genuinely operates in more than one town -- Casey's,
Hunt Brothers Pizza, a small regional bank with a branch in each of two
towns -- gets **one** file with `"towns"` (an array) instead of `"town"`,
plus a `"locations"` array carrying each branch's own address/phone
(other fields -- category, website, rating, photo -- are treated as
shared across every branch, since Google Maps generally does have a
separate `place_id`/rating/photo per physical branch, and only one gets
kept as representative):

```json
{
  "name": "Casey's",
  "category": "Restaurant & Food",
  "towns": ["Brookfield", "Marceline"],
  "source": "google_maps_merged",
  "website": "https://caseys.com",
  "rating": 4.2,
  "reviews": 150,
  "locations": [
    { "town": "Brookfield", "address": "123 Main St, Brookfield, MO", "phone": "(660) 555-0100" },
    { "town": "Marceline", "address": "456 Elm St, Marceline, MO", "phone": "(660) 555-0200" }
  ]
}
```

This listing shows up in `docs/directory.html` whenever any of its towns
is selected in the Towns filter (or when none are, same as any other
listing), and its card lists each branch's own address/phone separately
rather than picking just one.

**Don't merge on name alone.** Two businesses sharing a name across towns
is common and usually *not* the same company -- "First Baptist Church"
in Brookfield and "First Baptist Church" in Laclede are two unrelated
congregations, not branches of one; the same goes for lodges, civic
clubs, and (deliberately left as separate per-town listings) the Postal
Service, where each town's own address/phone is exactly the point.
Before merging, confirm it's a real chain (a recognizable commercial
brand, or -- like Delaney Funeral Home in Bucklin and Marceline --
already documented elsewhere in this codebase as one business). A
national franchise/kiosk brand riding inside a different local host
business at each location (a U-Haul Neighborhood Dealer, say) generally
shouldn't be merged either, since the underlying host is a different
real business at each site even though the franchise signage is the
same.
