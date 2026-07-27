# Manual (community-submitted) events

Each `.json` file in this directory is one **approved** community event,
created via [`docs/admin.html`](../../docs/admin.html) after reviewing a
submission from [`docs/submit.html`](../../docs/submit.html).

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
