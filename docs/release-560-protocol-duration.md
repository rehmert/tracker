# Release 560 — Protocol duration modes

The protocol editor supports:

- Start date and optional explicit end date.
- Start date and 1–520 whole weeks.

For weeks mode:

    end_date = start_date + (7 * weeks - 1) days

The end date is inclusive.

All three existing endpoints use the same parser:
- /protocols/{pid}/save
- /protocols/{pid}/add-item
- /protocols/{pid}/dates

No database migration is required.

Existing date-only submissions default to dates mode.

The existing horizon_weeks setting remains independent.

When editing a saved protocol, the exact stored dates
are displayed, with dates mode initially selected.
