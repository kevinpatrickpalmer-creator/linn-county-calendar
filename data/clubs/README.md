# Clubs & Classes posts

Each `.json` file in this directory is one **approved** post on the
public Clubs & Classes page (`docs/clubs.html`). `docs/submit-clubs.html`
posts to `apps-script/big-ideas.gs`, which commits this file
automatically once a submission is approved (reply "approved" to the
notification email, or edit the sheet directly -- see
`apps-script/README.md`).

This is a two-sided bulletin, same idea as Jobs Bulletin
(`data/jobs/README.md`) but for clubs and lessons instead of work: a
`"offering"` post is someone running a club or teaching a class and
looking for members or students (Red Hats, a bridge club, a kids'
spinning club, swimming lessons, a karate instructor, a woodworking
class); a `"looking"` post is someone who wants to join a club or find
an instructor. `name` holds whichever one applies -- the poster's own
name, or the club/class's name if it has one.

`build_clubs_directory.py` reads every file here and writes the
combined result to `docs/clubs.json`, which `docs/clubs.html` fetches
directly.

Rejected or still-pending submissions never get a file here -- there's
no "is this approved?" flag to check, so there's no way for an
unreviewed submission to leak into the public page.

Expected shape of each file:

```json
{
  "type": "offering",
  "name": "Marceline Bridge Club",
  "ageGroup": "Adults",
  "town": "Marceline",
  "description": "We meet Thursday evenings at the community center. Beginners welcome, we'll teach you.",
  "phone": "(660) 555-0142",
  "email": "kevin@example.com",
  "posted": "2026-09-19"
}
```

`type`, `name`, `ageGroup`, `town`, and `description` are required.
`type` is either `"offering"` (this person runs a club or teaches a
class, and wants members/students) or `"looking"` (this person wants
to join a club or find an instructor) -- `docs/clubs.html` groups
posts by this and badges each card, so it has to be one of those two
exact strings. `ageGroup` should match one of `club_age_groups` in
`docs/config.json` ("Kids", "Teens", "Adults", "All Ages") -- it's
what the page's filter uses. There's deliberately no fixed list of
club/class *types* (bridge, karate, spinning, swimming, woodworking,
whatever else) -- that range is too wide to pin down ahead of time, so
it just goes in `name`/`description` as free text.

**`posted`** is a `YYYY-MM-DD` date stamped at the moment of approval
by `apps-script/big-ideas.gs` -- not something the submitter enters --
so `docs/clubs.html` can sort newest-first and show "Posted X days
ago" on each card. A post also expires automatically after
`club_expiry_days` in `docs/config.json` (currently 60 days), and the
poster can pull their own post down early via
`docs/remove-listing.html` using the code they were given when they
posted -- see `removeListing()` in `apps-script/big-ideas.gs`. Either
way the file itself is left alone here; only
`build_clubs_directory.py`'s output changes.

**No street address field, deliberately** -- same reasoning as Jobs
Bulletin and Trading Post: these are people's homes and informal
meetups, not a business with posted hours. `description` is where a
poster says where/when it meets if that matters, and `phone`/`email`
are how the other side actually gets in touch.

**Town, not "Other":** same rule as the rest of the site -- see
`data/businesses/README.md` for the reasoning. The literal word
"Other" should never appear in a file here; `build_clubs_directory.py`
holds one back from the public site as a backstop if it ever does.

**`"example": true`** marks a post as a seeded sample rather than a
real submission -- for showing the format on an otherwise-empty board
so newcomers see what a good post looks like instead of a blank page.
`build_clubs_directory.py` pins it above every real post regardless of
date, and `docs/clubs.html` badges it "Example" and leaves it out of
the "N Posts" count so it never reads as real community activity. Its
`name` should say "(example)" too, and it should never carry a real
phone or email. Remove the file (or drop the flag) once there's enough
real activity that the board doesn't need it.
