# Tracker v2.3 — PK comparison export (increment 1)

Adds **Download comparison CSV** to the existing PK scenario comparison view.
The CSV contains the identical timestamp grid and baseline/scenario values produced by `/pk/compare`, with the existing compound, date-range, and scenario validation. Scenario labels are escaped against spreadsheet formula injection.

No database migration is required for this increment.

**Deployment caution:** This package is rebased onto the user-supplied tracker-main(2).zip source. It preserves that source’s existing backup retention implementation and updates its outdated backup-retention test. Compare against your deployed repository before applying; this package is not deployed to the server. Keep `.env`, `data/`, `backups/`, and `/tracker-backups/` intact.

Run `PYTHONPATH=. python -m pytest -q` before deploying.
