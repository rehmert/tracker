# Tracker v2.3 — PK comparison export (increment 1)

Adds **Download comparison CSV** to the existing PK scenario comparison view.
The CSV contains the identical timestamp grid and baseline/scenario values produced by `/pk/compare`, with the existing compound, date-range, and scenario validation. Scenario labels are escaped against spreadsheet formula injection.

No database migration is required for this increment.

**Deployment caution:** This package is derived from the prior v2.2 release archive, not a live checkout of GitHub main. Compare with your current repository before applying; do not overwrite newer changes. Keep `.env`, `data/`, `backups/`, and `/tracker-backups/` intact.

Run `pytest -q tests/test_pk_csv.py` and the full test suite before deploying.
