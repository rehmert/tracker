# Release 566 — Dose Log vial IDs, time-control layout and calendar selection

## User-visible corrections
- Dose Log's ordinary vial dropdown always displays the immutable **#vial ID**, including when a human-readable vial label is present. The compound, optional label, lot, status and remaining content are retained.
- The **When** field now occupies a full form grid row. Its 24-hour **Date**, **Time**, and **Use current time** controls use distinct grid cells on desktop; on mobile the button wraps below the inputs. The underlying named `taken_at` input and timestamp value are unchanged.
- Calendar → Log this dose prefers an eligible `in_use` vial. When none can supply the planned amount, it automatically selects the lowest-ID eligible `sealed` vial for that compound. Both paths validate the requested quantity and unit against that vial's inventory and recorded concentration. Explicit matching selections are retained.
- No changes to dose POST validation, recorded doses, purchase IDs, or database schema.

## Verification
- Expanded `tests/test_calendar_auto_vial.py` to assert sealed fallback.
- Added `tests/test_release566_dose_log_ux.py` to cover opened/lowest-ID sealed preference, insufficient inventory, incompatible units, stable IDs, and timestamp layout contract.
- Extended `tests/browser/test_navigation.py` with a *read-only* real Chromium check of date/time/button bounding boxes at 1440px, 800px and 390px and of the Use current time behavior.
- Qualification must occur on **tracker-dev**, using the existing `scripts/tracker-release.sh` isolated browser/backend, verified backup/restore and runtime checks. No GitHub Actions.
- PROD stays on Release 565 until exact-commit DEV qualification and visual acceptance, followed by signed promotion.
