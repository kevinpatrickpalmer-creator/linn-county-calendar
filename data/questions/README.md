# Ask the Community questions

Each `.json` file in this directory is one **approved** question on the
public Ask the Community page (`docs/ask-community.html`).
`docs/submit-question.html` posts to `apps-script/big-ideas.gs`, which
commits this file automatically once a submission is approved (reply
"approved" to the notification email, or edit the sheet directly -- see
`apps-script/README.md`).

This is the one board on the site with a real parent/child
relationship: an answer (`data/answers/README.md`) belongs to a
specific question here, referenced by this file's `id`. Every other
board publishes standalone listings; this is the only place
`build_questions_directory.py` has to join two directories together
before `docs/questions.json` is ready to ship.

`build_questions_directory.py` reads every file here, attaches that
question's approved answers from `data/answers/` as an `answers`
array, and writes the combined result to `docs/questions.json`, which
`docs/ask-community.html` fetches directly.

Rejected or still-pending submissions never get a file here -- there's
no "is this approved?" flag to check, so there's no way for an
unreviewed submission to leak into the public page.

Expected shape of each file:

```json
{
  "id": "6bda2e1a-5b89-4093-a2c5-17e56fc23baf",
  "town": "Marceline",
  "category": "Recommendations",
  "question": "Does anyone know someone who repairs old sewing machines?",
  "submitter_name": "Jane Smith",
  "photos": ["question-photos/pending-6bda2e1a-1.jpg"],
  "posted": "2026-09-20"
}
```

`town`, `question`, and `submitter_name` are required. `town` can be
`"All of Linn County"` (see `docs/submit-question.html`, same
mechanism as Trading Post/Jobs/Clubs & Classes) for a question that
isn't specific to one town -- most aren't. `category` is optional and
should match one of `question_categories` in `docs/config.json`, but a
question with an unrecognized or missing category still shows up
under "Other".

**`submitter_name` is who's asking, shown as "Asked by X"** -- unlike
most boards, phone and email are deliberately **not** collected here at
all. The point of a public answer (see `data/answers/README.md`) is
that anyone can help without the asker needing to be privately
reachable first; a person reviewing the submission can still follow up
by other means if something looks wrong with it.

**`id` is the full submission id (a UUID), not the usual 8-character
ref code** used elsewhere for matching an email reply -- this is the
value an answer's `question_id` has to match exactly, so it needs to
actually be unique on its own, not just unique-enough for that.

**`photos` is optional, up to 3** -- same upload mechanism as every
other board, see `data/lost-found/README.md` for the full explanation.
Genuinely useful here specifically ("does anyone know what this tool
is for") in a way it might not be everywhere else.

**Town, not "Other":** same rule as the rest of the site -- see
`data/businesses/README.md` for the reasoning. The literal word
"Other" should never appear in a file here;
`build_questions_directory.py` holds one back from the public site as
a backstop if it ever does.

A question also expires automatically -- `question_expiry_days` in
`docs/config.json` (currently 45 days) -- and the asker can pull their
own question down early via `docs/remove-listing.html` using the code
they were given when they posted, see `removeListing()` in
`apps-script/big-ideas.gs`. Either way the file itself is left alone
here; only `build_questions_directory.py`'s output changes. Removing a
question doesn't separately remove its answers' own source files in
`data/answers/`, they just stop being reachable/shown once
`build_questions_directory.py` can no longer join them to a published
question.

**`"example": true`** marks a question as a seeded sample rather than
a real submission -- for showing the format on an otherwise-empty
board so newcomers see what a good question (and a good answer) looks
like instead of a blank page. `build_questions_directory.py` pins it
above every real question regardless of date. Its `submitter_name`
should say "(example)" too. Remove the file (or drop the flag) once
there's enough real activity that the board doesn't need it.
