# Site backend (Google Apps Script)

Started as just the live backend for `docs/big-ideas.html` (votes have
to update in real time and be shared across everyone who visits, which
can't be a static file in this repo). Now also handles every other
board's submissions -- events, business directory, trading post, jobs,
clubs & classes, lost & found -- so approving one can happen by just replying
"approved" to an email, instead of clicking through to GitHub's
"create file" page by hand. `big-ideas.gs` is a small script that runs
for free inside a Google Sheet and does all of this, the same
Sheets-as-a-database idea already used for email alert sign-ups.

Setup only needs to happen **once**. Claude can't do this part -- it
has to happen in your own Google account (and, for the GitHub token
below, your own GitHub account).

## Setup

1. Go to [sheets.google.com](https://sheets.google.com) and create a
   new blank spreadsheet. Name it something like "Linn County Site
   Backend."
2. In that sheet, go to **Extensions &rarr; Apps Script**.
3. Delete whatever placeholder code is in the editor, and paste in
   the entire contents of `big-ideas.gs` (this folder).
4. Click the disk/Save icon.
5. Click **Deploy &rarr; New deployment**.
6. Click the gear icon next to "Select type" and choose **Web app**.
7. Fill in:
   - Description: anything, e.g. "Site backend"
   - Execute as: **Me**
   - Who has access: **Anyone**
8. Click **Deploy**. The first time, Google will show an
   "unverified app" warning because this is your own personal script,
   not a published one -- that's expected. Click **Advanced**, then
   **Go to [project name] (unsafe)**, then **Allow**.
9. Copy the **Web app URL** it gives you (starts with
   `https://script.google.com/macros/s/...`).
10. Send that URL back so it can be added to `docs/config.json` as
    `apps_script_api_url`. Nothing that depends on it works on the
    live site until that's set.

### GitHub token (needed for auto-approving events/directory/trading
post/jobs/lost & found -- not needed for Big Ideas, which only ever
writes to the sheet)

This lets the script commit an approved submission's file straight to
this repo, the same action you'd otherwise do by hand through GitHub's
"create new file" page.

1. On GitHub, go to **Settings &rarr; Developer settings &rarr; Fine-grained
   personal access tokens &rarr; Generate new token**.
2. Give it a name (e.g. "Site backend"), and set **Expiration** to
   whatever you're comfortable with (you'll just generate a new one
   and update the sheet if it ever expires).
3. Under **Repository access**, choose **Only select repositories**
   and pick just this one
   (`kevinpatrickpalmer-creator/linn-county-calendar`) -- not your
   whole account.
4. Under **Permissions &rarr; Repository permissions**, find
   **Contents** and set it to **Read and write**. Leave everything
   else as **No access**.
5. Click **Generate token**, and copy it (GitHub only shows it once).
6. Back in the Apps Script editor, click the gear icon (**Project
   Settings**) in the left sidebar, scroll to **Script Properties**,
   and click **Add script property**.
7. Property: `GITHUB_TOKEN`. Value: paste the token. Save. (This
   stays inside your own Apps Script project -- it's never in this
   repo, never in an email, never something Claude sees.)

If this token is missing or wrong, approving an event/directory/trading
post/jobs/clubs & classes/lost & found submission will fail with an
error saved right in the "Pending" sheet tab (see below) instead of
silently doing nothing.

## Day to day: approving submissions

Every real submission -- a Big Idea, or a post to any other board --
lands with `status` set to `pending` and stays invisible on the public
site until that changes to `approved`. Same manual-review principle
every board on this site has always had. Two ways to approve (or
reject) one:

- **Reply to the notification email** with just the word "approved"
  or "rejected" (anywhere in your reply). A check runs every 5
  minutes, reads that word back out of your reply, and handles it
  automatically -- for Big Ideas, updates the sheet; for everything
  else, commits the file straight to the site (or does nothing, if
  rejected). No need to open the sheet at all. If your reply is
  unclear (says neither word, or somehow both), it's left alone so you
  can just reply again or fix it by hand.
- **Edit the sheet directly**:
  - Big Ideas live in the **Ideas** tab -- change `status` from
    `pending` to `approved` (or `rejected`).
  - Everything else lives in the **Pending** tab -- same idea, though
    its fields are bundled into one `data_json` column since every
    board has a different shape. Changing `status` here by hand does
    *not* publish the file itself (that only happens through
    `checkForReplies`/the reply flow) -- for a board submission, hand-editing
    the sheet is really just a way to mark something as handled or to
    stop an in-progress reply-check from re-processing it, not a
    substitute publish path. If you'd rather publish by hand, use that
    board's `admin-*.html` page instead (still there, unchanged, as a
    fallback).

The reply-based check needs a one-time setup: in the Apps Script
editor, use the function dropdown near the top (next to Run/Debug) to
select **installReplyTrigger**, then click **Run**. Google will ask
you to re-authorize -- this time for Gmail access -- since reading
replies is a new permission beyond what the first setup granted; the
same "unverified app" warning from before is expected, click through
it the same way (**Advanced &rarr; Go to [project] (unsafe) &rarr;
Allow**). You only need to run this once, ever, not every deployment.

To remove something entirely (spam, duplicate, whatever) before it's
been approved, just delete its row from the sheet. Votes for a Big
Idea are tracked separately in the "Votes" tab and can be
ignored/left alone.

## Lost & Found photos

A photo attached to a Lost & Found submission is uploaded to
`docs/lost-found-photos/` right away (as part of submitting, before
review), sitting there unreferenced by any public listing until the
post is approved -- at which point the published JSON points to it. A
rejected post has its photo deleted again automatically.

## If the code ever needs to change

Update `big-ideas.gs` in this repo, then copy the new version into the
Apps Script editor (Extensions &rarr; Apps Script, from the same
sheet) and deploy again: **Deploy &rarr; Manage deployments &rarr;
edit (pencil icon) &rarr; New version &rarr; Deploy**. Using "New
version" instead of creating a whole new deployment keeps the same
Web app URL, so nothing on the site needs to change.
