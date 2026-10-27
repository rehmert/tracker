# Tracker v2.3 — Somatropin / IU support

- Added `compounds.primary_unit` (mg, mcg, g, or IU) with additive SQLite startup migration.
- Creating a compound named `Somatropin`, `Somatropin (HGH)`, or `HGH (Somatropin)` automatically selects IU. Existing matching compounds with no vials or IU vials are updated to IU on startup. Existing mass-tracked vials are not converted.
- Purchasing defaults the contents unit to the compound's selected unit; server validation prevents mass/IU mismatches.
- Vial edit validation preserves IU tracking; vial reconstitution calculator now labels and calculates IU and IU/mL for IU vials.
- Existing unit-aware administration, protocols, vial balances, and forecasts already support IU and remain unchanged.
- No automatic IU-to-mg conversion is performed; IU is its own dimension, preventing unintended conversions.
- New tests cover IU concentration arithmetic, purchasing, invalid mass input, and migration. Full suite: 125 passed.

## Deployment

Back up `/opt/tracker/data/tracker.db` and preserve `.env`, `data/`, `backups/`, and `/tracker-backups/`. Deploy the application code, then restart `tracker.service`. The additive migration runs at application startup.

## Usage

1. In Compounds, add `Somatropin (HGH)` (IU is selected automatically).
2. In a purchase, select Somatropin; enter vial contents in IU and price per vial.
3. Record reconstitution in mL; vial concentration and dose logging use IU/mL and IU.

This is a personal recordkeeping tool, not a dosing recommendation engine.
