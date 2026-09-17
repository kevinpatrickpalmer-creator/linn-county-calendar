# Trading Post listings

Each `.json` file in this directory is one **approved** listing on the
public Trading Post page (`docs/trading-post.html`).
`docs/submit-trading-post.html` posts to `apps-script/big-ideas.gs`,
which commits this file automatically once a submission is approved
(reply "approved" to the notification email, or edit the sheet
directly -- see `apps-script/README.md`).
[`docs/admin-trading-post.html`](../../docs/admin-trading-post.html)
still works as a manual fallback if that's ever needed instead.

This is for people selling things they raise, grow, or make on a small
scale, regularly, but who don't fit the main business directory (see
[`data/businesses/README.md`](../businesses/README.md)) because they
aren't a registered business -- sides of beef, raw goat milk, farm eggs,
fresh bread, honey, jam, garden produce, hay, firewood, quilts, soap, and
the like. There's no scraping for this section (Google Maps has no
listing for someone selling eggs out of their kitchen), so every file
here came through the submit/approve flow, same as `data/manual_events/`.

Labor and services (mowing, shoveling, moving, handyman-type work) are
**not** listed here -- that's a matching problem, not a goods listing, so
it has its own separate section: see
[`data/jobs/README.md`](../jobs/README.md).

`build_trading_post_directory.py` reads every file here and writes the
combined result to `docs/trading-post.json`, which `docs/trading-post.html`
fetches directly.

Rejected or still-pending submissions never get a file here -- there's no
"is this approved?" flag to check, so there's no way for an unreviewed
submission to leak into the public page.

Expected shape of each file:

```json
{
  "name": "Palmer Family Farm",
  "category": "Eggs & Dairy",
  "town": "Marceline",
  "phone": "(660) 555-0142",
  "email": "palmerfarm@example.com",
  "website": "https://www.facebook.com/palmerfamilyfarm",
  "availability": "Eggs available year-round, call ahead. Raw goat milk seasonal, April-October.",
  "description": "Farm fresh eggs $4/dozen. Raw goat milk $6/half gallon. Pickup at the farm off Route B, or we can meet in town."
}
```

Only `name` and `town` are required -- everything else may be omitted or
left blank. `category` should match one of `trading_post_categories` in
`docs/config.json` when possible (it's what the page's filter uses), but
a listing with an unrecognized or missing category still shows up under
"Other".

**No street address field, deliberately.** Unlike the business directory,
most of these are people's homes, not a storefront with posted hours --
publishing a home address by default isn't something a seller should have
to opt out of. `description` and `availability` are where a seller
describes pickup/delivery/market-stand details in their own words (e.g.
"pickup off Route B, text first" or "Saturdays at the Marceline farmers
market"), and `phone`/`email`/`website` are how a buyer actually reaches
them to work that out.

**Town, not "Other":** same rule as the business directory -- see
[`data/businesses/README.md`](../businesses/README.md) for the reasoning.
A submission's real town (including one typed into "Other" on
`docs/submit-trading-post.html`) always gets used; the literal word
"Other" should never appear in a file here, and
`build_trading_post_directory.py` holds one back from the public site as
a backstop if it ever does.

**`"example": true`** marks a listing as a seeded sample rather than a
real submission -- for showing the format on an otherwise-empty board
so newcomers see what a good listing looks like instead of a blank
page. `build_trading_post_directory.py` pins it above every real
listing regardless of name, and `docs/trading-post.html` badges it
"Example" and leaves it out of the "N Listings" count so it never
reads as real community activity. Its `name` should say "(example)"
too, and it should never carry a real phone, email, or website.
Remove the file (or drop the flag) once there's enough real activity
that the board doesn't need it.
