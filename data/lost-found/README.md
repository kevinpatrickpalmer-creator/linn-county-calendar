# Lost & Found posts

Each `.json` file in this directory is one **approved** post on the
public Lost & Found page (`docs/lost-found.html`), created via
[`docs/admin-lost-found.html`](../../docs/admin-lost-found.html) after
reviewing a submission from
[`docs/submit-lost-found.html`](../../docs/submit-lost-found.html).

Same two-sided shape as `data/jobs/` (a `"lost"` post and a `"found"`
post are the same fields, just opposite sides of the board) -- see
[`data/jobs/README.md`](../jobs/README.md) for the reasoning behind that
pattern. Kevin's ask, 2026-09-17, after a resident survey response
flagged this as something people actually wanted: a pet or an item,
lost or found, in one place instead of scattered across Facebook posts.

`build_lost_found_directory.py` reads every file here and writes the
combined result to `docs/lost-found.json`, which `docs/lost-found.html`
fetches directly.

Rejected or still-pending submissions never get a file here -- there's no
"is this approved?" flag to check, so there's no way for an unreviewed
submission to leak into the public page.

Expected shape of each file:

```json
{
  "type": "found",
  "category": "Pet",
  "name": "Gray tabby cat, white paws",
  "town": "Marceline",
  "date": "2026-09-15",
  "description": "Found near the intersection of Kansas and Ritchie. Very friendly, looks well cared for, no collar. Currently staying with us.",
  "contact_name": "Jane Smith",
  "phone": "(660) 555-0142",
  "posted": "2026-09-17",
  "photo": "lost-found-photos/gray-tabby-marceline.jpg"
}
```

`type`, `category`, `name`, `town`, `date`, and `description` are
required. `type` is either `"lost"` or `"found"` -- has to be one of
those two exact strings, same as `data/jobs/`'s `needed`/`offering`.
`category` should be one of `lost_found_categories` in `docs/config.json`
(`"Pet"`, `"Item"`, or `"Other"`).

**`name` is what's lost or found, not who's reporting it** -- unlike
`data/jobs/`, where `name` is the poster. A real lost & found board
headlines with the thing itself ("Gray tabby cat, white paws"), not the
reporter, since that's what a scanning reader is actually looking for.
The reporter's own name goes in `contact_name` instead, shown alongside
`phone`/`email` in the contact section of the card.

**`date`** is submitter-entered -- when the pet/item was actually lost
or found, which usually isn't the same day as the report. **`posted`**
is a separate `YYYY-MM-DD` stamped by `docs/admin-lost-found.html` at
the moment of approval, same purpose as `data/jobs/`'s `posted`: lets
`docs/lost-found.html` show "Posted X days ago" and sort newest-first,
independent of whatever date the submitter entered.

**`photo` is optional and, unlike every other photo on this site, isn't
a Google-hosted URL** -- there's no automated upload pipeline for a
submitter's own photo (the form only emails it to Kevin as an
attachment, same as every other field here goes through Web3Forms).
Publishing one is a manual step: upload the image into
`docs/lost-found-photos/` via GitHub's own "Add file → Upload files"
button (drag-and-drop, no git needed) *before* creating this JSON file,
then reference it here as a path relative to `docs/`, e.g.
`"lost-found-photos/whatever-you-named-it.jpg"` -- `docs/lost-found.html`
just points an `<img>` straight at that path. A post with no `photo`
field still publishes fine; the card just skips the image.

**No street address field, deliberately** -- same reasoning as
`data/jobs/` and Trading Post: `description` is where a poster says
where the pet/item was lost or found, if a specific location matters.

**Town, not "Other":** same rule as the rest of the site -- see
`data/businesses/README.md` for the reasoning. The literal word "Other"
should never appear in a file here; `build_lost_found_directory.py`
holds one back from the public site as a backstop if it ever does.

There's no automatic expiration here either -- when a pet's found or an
item's claimed, remove its file by hand via
[`docs/manage-lost-found.html`](../../docs/manage-lost-found.html), same
as everywhere else on this site.
