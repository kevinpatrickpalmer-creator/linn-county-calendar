# Manual (community-submitted) events

Each `.json` file in this directory is one **approved** community event.
`docs/submit.html` posts to `apps-script/big-ideas.gs`, which commits
this file automatically once a submission is approved (reply
"approved" to the notification email, or edit the sheet directly --
see `apps-script/README.md`). [`docs/admin.html`](../../docs/admin.html)
still works as a manual fallback if that's ever needed instead.

The scraper (`scrape_linn_county_calendar.py`) reads every file here on each
run and folds them into the same event list the CitySpark scrape produces,
so approved events show up in the next `.ics` regeneration automatically.

Rejected or still-pending submissions never get a file here — there's no
"is this approved?" flag to check, so there's no way for an unreviewed
submission to leak into the public calendar.

Expected shape of each file:

```json
{
  "name": "Ice Cream Social",
  "date": "2026-08-15",
  "time": "6:30 pm",
  "location": "Marceline, MO",
  "description": "Come get ice cream with the whole family."
}
```

`time`, `location`, and `description` may be omitted or left blank.

`date` is always the first occurrence, even for a recurring event. To
repeat (e.g. a club's standing monthly meeting), add `recurrence` (one of
`weekly`, `biweekly`, `monthly_weekday`, `monthly_date`) and `repeat_until`
(the last date it can occur, inclusive):

```json
{
  "name": "Linn County Republicans Meeting",
  "date": "2026-08-17",
  "time": "6:00 pm",
  "location": "Meadville, MO",
  "recurrence": "monthly_weekday",
  "repeat_until": "2027-08-31"
}
```

`monthly_weekday` repeats on the same week-and-day-of-month as `date`
(the 3rd Monday, here); `monthly_date` repeats on the same day-of-month
number instead. One file still covers the whole series -- the scraper's
`_expand_manual_event_dates()` turns it into one calendar entry per
occurrence at scrape time, so editing or cancelling the series (via
`docs/manage-events.html`) only ever touches this one file.
