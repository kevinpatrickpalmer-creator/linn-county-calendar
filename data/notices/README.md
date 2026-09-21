# Community Notices

Each `.json` file in this directory is one **approved** notice on the
public Community Notices page (`docs/notices.html`).
`docs/submit-notice.html` posts to `apps-script/big-ideas.gs`, which
commits this file automatically once a submission is approved (reply
"approved" to the notification email, or edit the sheet directly -- see
`apps-script/README.md`).

**Notice, not Calendar:** the calendar (`data/manual_events/`) is for
scheduled events with a date and time to show up to. This is for
short-lived information that isn't really an event at all -- a
business temporarily closed, the library closed one day, hours
changing for the holidays, a one-off public notice. If it has a
start/end time you'd add to a calendar, it belongs on the calendar
instead.

`build_notices_directory.py` reads every file here and writes the
combined result to `docs/notices.json`, which `docs/notices.html`
fetches directly.

Rejected or still-pending submissions never get a file here -- there's
no "is this approved?" flag to check, so there's no way for an
unreviewed submission to leak into the public page.

Expected shape of each file:

```json
{
  "town": "Marceline",
  "category": "Hours & Closures",
  "message": "The library will be closed Monday for a staff training day, reopening Tuesday at the normal time.",
  "submitter_name": "Marceline Public Library",
  "posted": "2026-09-21"
}
```

`town`, `message`, and `submitter_name` are required. `town` can be
`"All of Linn County"` (see `docs/submit-notice.html`, same mechanism
as Trading Post/Jobs/Clubs & Classes/Ask the Community) for something
that isn't specific to one town. `category` is optional and should
match one of `notice_categories` in `docs/config.json`, but a notice
with an unrecognized or missing category still shows up under "Other".

**`submitter_name` is who's posting the notice** (often a business or
organization name, e.g. "Marceline Public Library", sometimes just a
person) -- shown as "Posted by X". No phone or email collected here on
purpose, same reasoning as Ask the Community: a notice is something
people should know, not something that needs a private reply.

**`photos` is optional, up to 3** -- same upload mechanism as every
other board, see `data/lost-found/README.md` for the full explanation.

**Town, not "Other":** same rule as the rest of the site -- see
`data/businesses/README.md` for the reasoning. The literal word
"Other" should never appear in a file here; `build_notices_directory.py`
holds one back from the public site as a backstop if it ever does.

**A notice expires fast on purpose** -- `notice_expiry_days` in
`docs/config.json` (currently 14 days, shorter than every other
board's window) reflects that this content is meant to be short-lived
by definition. The poster can also pull it down early via
`docs/remove-listing.html` using the code they were given when they
posted, see `removeListing()` in `apps-script/big-ideas.gs`. Either
way the file itself is left alone here; only
`build_notices_directory.py`'s output changes.

**`"example": true`** marks a notice as a seeded sample rather than a
real submission -- for showing the format on an otherwise-empty board
so newcomers see what a good notice looks like instead of a blank
page. `build_notices_directory.py` pins it above every real notice
regardless of date. Its `submitter_name` should say "(example)" too.
Remove the file (or drop the flag) once there's enough real activity
that the board doesn't need it.
