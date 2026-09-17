# Big Ideas Board backend (Google Apps Script)

`docs/big-ideas.html` needs somewhere live to store ideas and vote
counts -- unlike the rest of this site, that can't be a static file in
this repo, because votes have to update in real time and be shared
across everyone who visits. `big-ideas.gs` is a small script that runs
for free inside a Google Sheet and does that job, the same
Sheets-as-a-database idea already used for email alert sign-ups.

This only needs to be set up **once**. Claude can't do this part --
it has to happen in your own Google account.

## Setup

1. Go to [sheets.google.com](https://sheets.google.com) and create a
   new blank spreadsheet. Name it something like "Linn County Big
   Ideas."
2. In that sheet, go to **Extensions &rarr; Apps Script**.
3. Delete whatever placeholder code is in the editor, and paste in
   the entire contents of `big-ideas.gs` (this folder).
4. Click the disk/Save icon.
5. Click **Deploy &rarr; New deployment**.
6. Click the gear icon next to "Select type" and choose **Web app**.
7. Fill in:
   - Description: anything, e.g. "Big Ideas API"
   - Execute as: **Me**
   - Who has access: **Anyone**
8. Click **Deploy**. The first time, Google will show an
   "unverified app" warning because this is your own personal script,
   not a published one -- that's expected. Click **Advanced**, then
   **Go to [project name] (unsafe)**, then **Allow**.
9. Copy the **Web app URL** it gives you (starts with
   `https://script.google.com/macros/s/...`).
10. Send that URL back so it can be added to `docs/config.json` as
    `big_ideas_api_url`. The board won't work on the live site until
    that's set.

## Day to day: approving ideas

Every real submission lands in the "Ideas" tab of your sheet with
`status` set to `pending`, and you'll get an email when one comes in.
It stays invisible on the public page until that changes to
`approved` -- same manual-review principle as approving a Trading
Post listing or job post, just done in a spreadsheet cell instead of
a GitHub file. Two ways to do that:

- **Reply to the email** with just the word "approved" or "rejected"
  (anywhere in your reply). A check runs every 5 minutes, reads that
  word back out of your reply, and updates the sheet automatically --
  no need to open the sheet at all. If your reply is unclear (says
  neither word, or somehow both), it's left alone so you can just
  reply again or fix the cell by hand.
- **Edit the sheet directly** -- change that one cell from `pending`
  to `approved` (or `rejected`) yourself, same as before.

The reply-based check needs a one-time setup: in the Apps Script
editor, use the function dropdown near the top (next to Run/Debug) to
select **installReplyTrigger**, then click **Run**. Google will ask
you to re-authorize -- this time for Gmail access -- since reading
replies is a new permission beyond what the first setup granted; the
same "unverified app" warning from before is expected, click through
it the same way (**Advanced &rarr; Go to [project] (unsafe) &rarr;
Allow**). You only need to run this once, ever, not every deployment.

To remove an idea entirely (spam, duplicate, whatever), just delete
its row. Votes for it are tracked separately in the "Votes" tab and
can be ignored/left alone.

## If the code ever needs to change

Update `big-ideas.gs` in this repo, then copy the new version into the
Apps Script editor (Extensions &rarr; Apps Script, from the same
sheet) and deploy again: **Deploy &rarr; Manage deployments &rarr;
edit (pencil icon) &rarr; New version &rarr; Deploy**. Using "New
version" instead of creating a whole new deployment keeps the same
Web app URL, so nothing on the site needs to change.
