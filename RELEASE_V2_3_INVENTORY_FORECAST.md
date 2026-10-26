# Tracker v2.3 — Inventory forecasting increment

- Adds read-only compound and consumable depletion outlook to `/inventory-intelligence`.
- Historical usage windows: 30, 90, or 180 calendar days.
- Aggregates active, unexpired vial inventory by compound and unit dimension. Excludes expired and past-beyond-use vials.
- Uses recorded administered amounts (not waste) to estimate compound consumption; uses recorded supply usage for consumables.
- Highlights estimated depletion within 21 days. Without consumption history, displays an explicit unknown state.
- No database migration; does not change inventory, protocols, or medical records.
- Existing PK CSV, audit, Health Insights and multi-compound PK overlay retained.

## Validation
Focused tests: 4 passed. Full suite was attempted but did not complete within the available execution window; run `python -m pytest -q` in the deployment environment.

## Deploy
Review and merge into your Git checkout, preserving `.env`, `data/`, `backups/` and `/tracker-backups/`. Run tests and back up the database before restarting the service.
