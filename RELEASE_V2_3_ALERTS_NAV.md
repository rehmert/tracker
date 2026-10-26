# Tracker v2.3 — Inventory alerts and sortable navigation

- New `/inventory-alerts` read-only alert center for expiration, beyond-use, and estimated depletion.
- Select historical consumption window (30/90/180 days) and alert horizon (7/14/21/30/60/90 days).
- Navigation order can be default, alphabetical, or manually reordered using accessible up/down buttons.
- Custom order is saved in browser localStorage (per browser/device), not in SQLite.
- No schema migration. No automated notifications or new dosing logic.
- Integrate through Git; preserve `.env`, `data/`, `backups/`, and `/tracker-backups/`.
