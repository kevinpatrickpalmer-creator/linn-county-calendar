# Local Alerts

Each `.json` file in this directory is one **approved** alert on the
public Local Alerts page (`docs/local-alerts.html`).
`docs/submit-alert.html` posts to `apps-script/big-ideas.gs`, which
commits this file automatically once a submission is approved (reply
"approved" to the notification email, or edit the sheet directly -- see
`apps-script/README.md`).

**More urgent than a Notice, not the same thing** -- a Notice
(`data/notices/README.md`) is routine, short-lived info (hours
changing, a one-day closure). This is for the stuff people need to
know about *right now*: a water main break, a road closure, a boil
water order, a power outage, anything with real safety or
day-to-day-life stakes. Built with the expectation that a city or
county department, not just a resident, is often the one posting
(Kevin's framing, 2026-09-21: "imagine that the city's likely going to
use this tool") -- `submitter_name` is expected to often be something
like "City of Marceline" or "Marceline Water Department" rather than a
person's name, though nothing stops a resident from posting one too.

`build_alerts_directory.py` reads every file here and writes the
combined result to `docs/local-alerts.json`, which
`docs/local-alerts.html` fetches directly.

Rejected or still-pending submissions never get a file here -- there's
no "is this approved?" flag to check, so there's no way for an
unreviewed submission to leak into the public page. That review step
is also the site's only real safeguard against a false or prank alert
going live, same as every other board -- there's no separate
verification system for who's allowed to post one.

Expected shape of each file:

```json
{
  "category": "Boil Water Order",
  "town": "Marceline",
  "message": "A boil water order is in effect for the north side of town due to a water main break on Kansas Ave. Boil tap water for at least one minute before drinking or cooking until further notice.",
  "submitter_name": "City of Marceline",
  "posted": "2026-09-21"
}
```

`category`, `town`, `message`, and `submitter_name` are required.
`category` should match one of `alert_categories` in
`docs/config.json` ("Road Closure or Traffic", "Power or Utility
Outage", "Boil Water Order", "Weather or Severe Conditions", "Public
Safety", "Other"). `town` can be `"All of Linn County"` (see
`docs/submit-alert.html`, same mechanism as every other board with a
town field) for something that isn't specific to one town, a
countywide weather event, for instance. No phone or email collected
here on purpose, same reasoning as Notices: this is a broadcast, not
something that needs a private reply.

**`photos` is optional, up to 3** -- same upload mechanism as every
other board, see `data/lost-found/README.md` for the full explanation.
A photo of a closure sign or actual conditions can matter more here
than almost anywhere else on the site.

**Town, not "Other":** same rule as the rest of the site -- see
`data/businesses/README.md` for the reasoning. The literal word
"Other" should never appear in a file here; `build_alerts_directory.py`
holds one back from the public site as a backstop if it ever does.

**An alert expires fast on purpose** -- `alert_expiry_days` in
`docs/config.json` (currently 5 days, the shortest window on the
site) reflects that a days-old alert about a road that's since
reopened isn't just stale, it's actively misleading. The poster can
also pull it down early via `docs/remove-listing.html` using the code
they were given when they posted, see `removeListing()` in
`apps-script/big-ideas.gs` -- worth doing as soon as whatever prompted
the alert is actually resolved, rather than waiting out the window.
Either way the file itself is left alone here; only
`build_alerts_directory.py`'s output changes.

**`"example": true`** marks an alert as a seeded sample rather than a
real submission -- for showing the format on an otherwise-empty board
so newcomers see what a good alert looks like instead of a blank page.
`build_alerts_directory.py` pins it above every real alert regardless
of date. Its `submitter_name` should say "(example)" too. Remove the
file (or drop the flag) once there's enough real activity that the
board doesn't need it.
