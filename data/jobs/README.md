# Jobs Bulletin posts

Each `.json` file in this directory is one **approved** post on the
public Jobs Bulletin page (`docs/jobs.html`). `docs/submit-job.html`
posts to `apps-script/big-ideas.gs`, which commits this file
automatically once a submission is approved (reply "approved" to the
notification email, or edit the sheet directly -- see
`apps-script/README.md`). [`docs/admin-job.html`](../../docs/admin-job.html)
still works as a manual fallback if that's ever needed instead.

This is a two-sided bulletin matching people who need help (shoveling
snow, mowing, moving, handyman-type work, or a local business with a
shift to fill) with people willing to do that work, whether that's an
experienced handyman or a teenager looking to pick up odd jobs -- the
kind of thing that used to live on a corkboard at the feed store. A
`"needed"` post is the same shape whether it comes from a homeowner or
a business that's hiring -- `name` just holds whichever one applies (see
below). This directory is **not** where a business lists itself
permanently as a business (see
[`data/businesses/README.md`](../businesses/README.md)) and **not** for
goods for sale (see [`data/trading-post/README.md`](../trading-post/README.md)),
just work, offered or needed.

`build_jobs_directory.py` reads every file here and writes the combined
result to `docs/jobs.json`, which `docs/jobs.html` fetches directly.

Rejected or still-pending submissions never get a file here -- there's no
"is this approved?" flag to check, so there's no way for an unreviewed
submission to leak into the public page.

Expected shape of each file:

```json
{
  "type": "needed",
  "name": "Kevin P.",
  "category": "Yard Work & Snow Removal",
  "town": "Marceline",
  "description": "Need my driveway and sidewalk shoveled after each snow this winter. I'm elderly and can't do it myself anymore.",
  "phone": "(660) 555-0142",
  "email": "kevin@example.com",
  "posted": "2026-09-15"
}
```

`type`, `name`, `town`, and `description` are required. `type` is either
`"needed"` (this person, or business, needs help) or `"offering"` (this
person is offering to do the work) -- `docs/jobs.html` groups posts by
this and badges each card, so it has to be one of those two exact
strings. `name` holds whatever the poster goes by publicly -- a person's
name for most posts, or a business name for a company posting an
opening. `category` should match one of `job_categories` in
`docs/config.json` when possible (it's what the page's filter uses), but
a post with an unrecognized or missing category still shows up under
"Odd Jobs / Other".

**`posted`** is a `YYYY-MM-DD` date stamped at the moment of approval
(by `apps-script/big-ideas.gs`, or by `docs/admin-job.html` if the
manual fallback is used instead) -- not something the submitter enters -- so
`docs/jobs.html` can sort newest-first and show "Posted X days ago" on
each card. Unlike a business or Trading Post listing, a jobs post goes
stale (the snow melted, the move happened) in a way that matters to a
browsing reader, so this date is what makes that staleness visible at a
glance. A post also expires automatically after `job_expiry_days` in
`docs/config.json` (currently 30 days), and the poster can pull their
own post down early via `docs/remove-listing.html` using the code they
were given when they posted -- see `removeListing()` in
`apps-script/big-ideas.gs`. Either way the file itself is left alone
here; only `build_jobs_directory.py`'s output changes. A post can
still be removed by hand via
[`docs/manage-job.html`](../../docs/manage-job.html) if needed.

**No street address field, deliberately** -- same reasoning as the
Trading Post: these are people's homes, not a business with posted
hours. `description` is where a poster says where the work is if that
matters, and `phone`/`email` are how the other side actually gets in
touch.

**Town, not "Other":** same rule as the rest of the site -- see
`data/businesses/README.md` for the reasoning. The literal word "Other"
should never appear in a file here; `build_jobs_directory.py` holds one
back from the public site as a backstop if it ever does.

**`"example": true`** marks a post as a seeded sample rather than a
real submission -- for showing the format on an otherwise-empty board
so newcomers see what a good post looks like instead of a blank page.
`build_jobs_directory.py` pins it above every real post regardless of
date, and `docs/jobs.html` badges it "Example" and leaves it out of
the "N Posts" count so it never reads as real community activity. Its
`name` should say "(example)" too, and it should never carry a real
phone or email. Remove the file (or drop the flag) once there's enough
real activity that the board doesn't need it.
