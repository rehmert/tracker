# Tracker v2.3 — Protocol date save fix

The protocol editor previously had a separate `/dates` form. Clicking **Save protocol** or **Save & add another** did not include the dates in the submitted payload. The start/end date fields are now in the primary protocol form, and both save routes persist them alongside the protocol items.

- Existing date validation is shared by the old dates endpoint and the primary save path.
- Invalid date ranges return HTTP 400 without committing edits.
- Existing protocol records and dates are retained.
- No schema migration is required.
- Tests: 131 passed (`PYTHONPATH=. pytest -q`).

Deployment: back up your SQLite database and uploads, deploy the updated code without overwriting `.env`, `data/`, `backups/`, or external backup directories, restart `tracker.service`, and hard-refresh your browser.
