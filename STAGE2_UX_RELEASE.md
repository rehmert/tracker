# Tracker UX — Stage 2 incremental release

## Delivered
- Unified Inventory Health landing page now includes actionable inventory alerts, existing KPIs, forecasts and vial detail inspection in one view. The legacy `/inventory-alerts` route remains available for adjustable alert horizons.
- Inventory Health navigation jumps directly to attention, forecasts, or vial details.
- Inventory search filter persists within the browser tab, without server-side data changes.
- Protocol editor warns when leaving with unsaved edits; intentional form submissions are not interrupted.

## Not included in this stage
Guided purchase/blend wizards, persistent database-backed audit trails, global saved views, and data schema changes require separate development and integration testing.

## Deployment
Stop Tracker, back up data, unzip the small patch over `/opt/tracker`, start Tracker, and hard-refresh the browser. No database migration.
