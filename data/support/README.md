# Community Support posts

Each `.json` file in this directory is one **approved** post on the
public Community Support page (`docs/support.html`).
`docs/submit-support.html` posts to `apps-script/big-ideas.gs`, which
commits this file automatically once a submission is approved (reply
"approved" to the notification email, or edit the sheet directly -- see
`apps-script/README.md`).

**Not anonymous, and deliberately not routed privately through an
admin** -- this board works the same way every other board on the
site does: the poster provides their own contact info, and whoever
wants to help reaches out to them directly. Kevin's call, 2026-09-21,
after an earlier design (private intake, requests never public, routed
through an admin/partner org as an intermediary) was scrapped as
overthinking it -- the site is already low-friction/no-accounts, and
someone in need "meets the community halfway" by providing a phone
number or email, the same trade every other poster on this site
already makes.

**Benefit dinners and fundraisers are a category here, not a separate
board** -- the original brainstorm doc had "Benefits/Fundraisers" as
its own maybe-a-board item, but a benefit dinner for someone's medical
bills is really the same kind of post as a direct request, just
organized as an event instead of a personal ask. See
`"Benefit or Fundraiser"` in `support_categories` below.

**Two-sided like `data/jobs/` and `data/volunteer/`** (added the same
day as the board itself, once Kevin pointed out an organization with a
standing resource needs a place to say "we're here" too) -- a
`"needed"` post is someone (or a neighbor posting on their behalf)
asking for help; an `"offering"` post is an organization, church, or
program saying what it offers on an ongoing basis (a food pantry's
open hours, a clothing drive, a charity's contact info). Same fields
either way, `name`/`description` just mean something slightly
different depending on which side it's on -- see
`docs/submit-support.html` for the exact relabeling.

`build_support_directory.py` reads every file here and writes the
combined result to `docs/support.json`, which `docs/support.html`
fetches directly.

Rejected or still-pending submissions never get a file here -- there's
no "is this approved?" flag to check, so there's no way for an
unreviewed submission to leak into the public page.

Expected shape of each file:

```json
{
  "type": "needed",
  "category": "Medical",
  "name": "The Palmer Family",
  "town": "Marceline",
  "description": "My husband had emergency surgery last week and we're behind on bills while he recovers. Any help with groceries or utilities would mean a lot.",
  "phone": "(660) 555-0142",
  "posted": "2026-09-21"
}
```

`type`, `category`, `name`, `town`, and `description` are required.
`type` is either `"needed"` (asking for help) or `"offering"` (an
organization's standing resource) -- `docs/support.html` groups posts
by this and badges each card, so it has to be one of those two exact
strings, same rule as `data/jobs/`/`data/volunteer/`. `category`
should match one of `support_categories` in `docs/config.json`
("Bills & Living Expenses", "Medical", "Food", "Clothing & School
Supplies", "Transportation", "Benefit or Fundraiser", "Other").
Unlike most boards, `category` is required here rather than optional
-- what kind of help is needed or offered matters more on this board
than anywhere else on the site, both for a browsing helper deciding
whether they can pitch in and for `docs/support.html`'s category
filter.

**`name` is who the post is about, not necessarily who's typing it** --
a family, a person, or an organization's name, depending on `type`.
Someone can post a `"needed"` request on a neighbor's behalf; the
field doesn't distinguish who physically submitted the form.
`description` shifts meaning the same way: what's needed for a
`"needed"` post, what's offered (hours, how to access it, who to
contact) for an `"offering"` post.

**At least a phone or email is expected**, same "meet the community
halfway" reasoning as the README's intro above -- this isn't enforced
as a hard requirement server-side (matching every other board, where
the client-side form is what actually requires at least one), but a
post with neither is much less useful to a helper who wants to reach
out directly.

**`photos` is optional, up to 3** -- same upload mechanism as every
other board, see `data/lost-found/README.md` for the full explanation.
Useful for a benefit dinner flyer, for instance.

**Town, not "Other":** same rule as the rest of the site -- see
`data/businesses/README.md` for the reasoning. The literal word
"Other" should never appear in a file here; `build_support_directory.py`
holds one back from the public site as a backstop if it ever does.

A post also expires automatically -- `support_expiry_days` in
`docs/config.json` (currently 30 days) -- and the poster can pull their
own post down early via `docs/remove-listing.html` using the code they
were given when they posted, see `removeListing()` in
`apps-script/big-ideas.gs`. Either way the file itself is left alone
here; only `build_support_directory.py`'s output changes.

**`"example": true`** marks a post as a seeded sample rather than a
real submission -- for showing the format on an otherwise-empty board
so newcomers see what a good post looks like instead of a blank page.
`build_support_directory.py` pins it above every real post regardless
of date, and `docs/support.html` badges it "Example" and leaves it out
of the "N Posts" count so it never reads as a real person's real
situation. Its `name` should say "(example)" too, and it should never
carry a real phone or email. Remove the file (or drop the flag) once
there's enough real activity that the board doesn't need it.
