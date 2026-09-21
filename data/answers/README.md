# Ask the Community answers

Each `.json` file in this directory is one **approved** answer to a
question in `data/questions/`. `docs/submit-answer.html` posts to
`apps-script/big-ideas.gs` the same way every other submit page does
(same review/approve pipeline, same removal-code self-service), just
under board `"answer"` instead of `"question"`.

An answer is never shown on its own -- it only appears nested under
its question, attached by `build_questions_directory.py` when it
builds `docs/questions.json`. See `data/questions/README.md` for why
this is the one board on the site with this parent/child shape.

Rejected or still-pending submissions never get a file here, same
"no approved flag, no leak" reasoning as everywhere else.

Expected shape of each file:

```json
{
  "id": "8f2c1a90-4e3b-4a11-9c7d-2b5e6f7a8b9c",
  "question_id": "6bda2e1a-5b89-4093-a2c5-17e56fc23baf",
  "answer": "Try Dale's Sewing & Vacuum in Brookfield, he's fixed two of ours.",
  "submitter_name": "Kevin P.",
  "posted": "2026-09-21"
}
```

`question_id`, `answer`, and `submitter_name` are required.
**`question_id` has to exactly match the `id` field of a file in
`data/questions/`** -- it's how `build_questions_directory.py` knows
which question this belongs under. `docs/submit-answer.html` fills
this in automatically from the `?id=` in its own URL (which
`docs/ask-community.html`'s "Answer this" link sets), a submitter
never types or sees this value.

**An answer whose `question_id` doesn't match any currently-published
question is silently dropped**, not published as an orphan and not
treated as an error -- this happens naturally whenever the question it
answered has since expired, been removed, or (in theory) never
existed. The source file is left alone either way, same "the file
stays, only the published output changes" pattern as an expired
question.

No `town`, `category`, or `photos` here -- an answer inherits all of
that from its question by definition, repeating it would just be
redundant. No phone/email collected either, same reasoning as
`data/questions/README.md`: the point of answering publicly is that
nobody needs to be privately reachable for this to work.

An answer can be pulled down by whoever posted it via
`docs/remove-listing.html` (board `answer`) using their own removal
code, same self-service mechanism as everywhere else, independent of
whether the question itself still exists.
