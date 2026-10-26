# Tracker Release 5 — Health Intelligence & Custom Supply Categories

## Included
- Health timeline at `/health-timeline` combining actual vital measurements, administrations, waste logs, laboratory reports and scheduled protocol start/end dates. Protocol dates are explicitly labeled as scheduled, not actual doses.
- Individual lab analyte trends at `/labs/trends/{key}`. Uses existing analyte normalization and compatible unit conversions; original lab values and reference intervals remain visible.
- New supply categories: needles, syringes, sterile empty vials, pen cartridges, alcohol swabs, other disposables, plus existing BAC water and pills.
- Create additional categories and choose unit (count, boxes, packs, mL, L, mg, g) at `/supplies`.
- Purchase supply add/edit forms accept new categories, and inventory usage retains history.
- Existing PK Simulator remains available unchanged, including saved scenario comparison. No dosing advice is generated.

## Deployment
Back up the database and uploads using the existing Backups page. Deploy files, preserving `.env`, `data/`, and uploads. Restart `tracker.service` and hard-refresh the browser.

**Database:** A new `supply_categories` table is created automatically on startup by SQLAlchemy `create_all`. No destructive migration. Existing `supplies.kind` values (`bac_water`, `pill`) remain valid. Built-in categories are created on first visit to Supplies or a purchase detail page. Category keys fit the existing 20-character `supplies.kind` column.

**Important:** Categories are added from the Supplies page. Purchases remain the source of purchased stock; record use on Supplies. Quantity for count-unit categories must be an integer; fractional quantities are permitted for measured units. Existing consumed quantities cannot be erased by editing a purchase.

**No external health-data integrations.**
