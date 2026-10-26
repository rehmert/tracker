# Release 3 calendar upgrade

- Active protocols now have optional start and end dates. Set them in each protocol editor.
- Existing active protocols are **not** assigned guessed start dates; the calendar shows a link to set them.
- The calendar automatically projects dates from each active protocol start date; no month-specific anchor is required.
- Same-day, same-compound dose logs reconcile to projected events. This is a display association, **not** dose/amount verification. Extra logged doses remain visible.
- Past projected entries without a matching log show **not recorded**, rather than claiming a missed administration.
- Forecasts, dose logs, and inventory remain untouched.
- Migration is additive and repeatable (`protocols.start_date`, `protocols.end_date`). Back up SQLite before deployment.
