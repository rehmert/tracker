# Release 2 — Intelligent Dashboard

- Active/what-if toggle in each protocol editor. Existing plans remain what-if until explicitly activated.
- Dashboard protocol table with per-compound dose, frequency, inventory and dose count.
- Inventory depletion forecast from combined active protocol usage; excludes expired/discarded stock.
- 7/30-day vital averages and 30-day changes, plus 30/90/365-day weight, BP and pulse charts.
- Additive migration for `protocols.is_active`.

## Install
Back up your SQLite database and uploads. Deploy code preserving `.env`, `data/` and uploads. Restart Tracker. Mark current protocols active from their editor pages, then visit Overview.

## Limits
Forecast assumes unchanged usage and no new purchases, waste or earlier expiry. Volume-only doses cannot be converted to mass without concentration. Vitals are descriptive, not clinical assessments. No external health synchronization is included.
