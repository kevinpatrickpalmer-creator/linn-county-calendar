# Volunteer & Help Needed posts

Each `.json` file in this directory is one **approved** post on the
public Volunteer & Help Needed page (`docs/volunteer.html`).
`docs/submit-volunteer.html` posts to `apps-script/big-ideas.gs`, which
commits this file automatically once a submission is approved (reply
"approved" to the notification email, or edit the sheet directly -- see
`apps-script/README.md`).

Same two-sided shape as `data/jobs/` (a `"needed"` post and an
`"offering"` post are the same fields, just opposite sides of the
board) -- see `data/jobs/README.md` for the reasoning behind that
pattern. **Kept separate from Jobs Bulletin on purpose**: browsing for
paid work and browsing for a volunteer opportunity are different asks,
mixing them would make both boards worse (Kevin's call, 2026-09-21).
This is for volunteer time and skills, not paid work -- cleanup
projects, an event needing helpers, a community organization needing
assistance, someone offering their time or skills.

`build_volunteer_directory.py` reads every file here and writes the
combined result to `docs/volunteer.json`, which `docs/volunteer.html`
fetches directly.

Rejected or still-pending submissions never get a file here -- there's
no "is this approved?" flag to check, so there's no way for an
unreviewed submission to leak into the public page.

Expected shape of each file:

```json
{
  "type": "needed",
  "name": "Marceline Park Cleanup Committee",
  "category": "Cleanup & Outdoor",
  "town": "Marceline",
  "description": "Looking for 10-15 volunteers for the fall cleanup day at the park, Saturday morning. Bring gloves if you have them, we'll have trash bags and tools.",
  "phone": "(660) 555-0142",
  "posted": "2026-09-21"
}
```

`type`, `name`, `town`, and `description` are required. `type` is
either `"needed"` (this person or organization needs volunteers) or
`"offering"` (this person is offering their own time/skills) --
`docs/volunteer.html` groups posts by this and badges each card, so it
has to be one of those two exact strings. `name` holds whatever the
poster goes by publicly -- an organization or event name for most
"needed" posts, a person's name for most "offering" posts. `category`
should match one of `volunteer_categories` in `docs/config.json` when
possible (it's what the page's filter uses), but a post with an
unrecognized or missing category still shows up under "Other".

**`posted`** is a `YYYY-MM-DD` date stamped at the moment of approval
(by `apps-script/big-ideas.gs`) -- not something the submitter enters --
so `docs/volunteer.html` can sort newest-first and show "Posted X days
ago" on each card. A post also expires automatically after
`volunteer_expiry_days` in `docs/config.json` (currently 30 days, same
window as Jobs), and the poster can pull their own post down early via
`docs/remove-listing.html` using the code they were given when they
posted -- see `removeListing()` in `apps-script/big-ideas.gs`. Either
way the file itself is left alone here; only
`build_volunteer_directory.py`'s output changes.

**`photos` is optional, up to 3** -- same upload mechanism as every
other board, see `data/lost-found/README.md` for the full explanation.

**Town, not "Other":** same rule as the rest of the site -- see
`data/businesses/README.md` for the reasoning. The literal word
"Other" should never appear in a file here; `build_volunteer_directory.py`
holds one back from the public site as a backstop if it ever does.

**`"example": true`** marks a post as a seeded sample rather than a
real submission -- for showing the format on an otherwise-empty board
so newcomers see what a good post looks like instead of a blank page.
`build_volunteer_directory.py` pins it above every real post regardless
of date, and `docs/volunteer.html` badges it "Example" and leaves it
out of the "N Posts" count so it never reads as real community
activity. Its `name` should say "(example)" too, and it should never
carry a real phone or email. Remove the file (or drop the flag) once
there's enough real activity that the board doesn't need it.
