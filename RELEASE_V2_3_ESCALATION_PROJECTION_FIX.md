# Protocol escalation projection correction

The Today/Upcoming dashboard previously ignored protocol item start_week/end_week and weekday selection. Both dashboard and calendar now call `staged_occurrences` in `app/calendar.py` to anchor escalation windows to protocol.start_date. Week 1 covers days 0–6, week 2 days 7–13, etc. End week is inclusive. Calendar date filtering and dose log reconciliation remain unchanged.

No database migration. Back up the database and existing app files before deploying. Restart `tracker.service` and hard-refresh browser.

Tests: 142 passed, 1 pre-existing unrelated HTML title assertion failed (also failed in previous release). New escalation regression tests passed.
