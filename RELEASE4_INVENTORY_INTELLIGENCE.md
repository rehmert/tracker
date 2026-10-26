# Release 4 — Inventory Intelligence

Built on Release 3. No database migration required.

## Features
- New **Inventory insights** sidebar page with expiring/expired/low-stock indicators.
- Searchable, expandable vial rows with administered amount, recorded waste, and allocated costs.
- Inventory analytics use existing vial, purchase, and dose/waste records; no external integrations.
- Cost per administered dose is available by dividing a vial's administered cost by its recorded dose count (where nonzero); the page displays the count and total administered cost.
- Expiration alerts are displayed on the page; they are not scheduled notifications.

## Deployment
Back up your database and uploads. Extract over the application while preserving `.env`, `data/`, and user uploads. Restart `sudo systemctl restart tracker.service`; hard-refresh browser with Ctrl+Shift+R.

## Interpretation
Expiration dates are user-entered. Expired vials remain visible for audit. Low-stock threshold is 20% of vial contents. Waste amounts are based on explicit `kind=waste` records, not automatically inferred from discarded status. Cost is estimated using existing landed-cost allocation.
