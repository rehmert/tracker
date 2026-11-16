# Release 641 — Correct food duplicate logs and default missing nutrients to zero

## Scope and behavior

- The existing **Review Duplicates** page can now suggest near matches when the
  first two meaningful food-name words match, as well as exact names/barcodes.
  A suggestion is never automatically merged.
- **Reassign logged uses** transfers every historic meal entry of a selected
  duplicate version to the explicitly selected keeper, in one SQL transaction.
  It checks the displayed use count against the current database. Dates, meals,
  entry IDs and recorded serving counts remain intact. **Historic nutrition
  totals intentionally change** to use the chosen keeper's per-serving values.
- Once all logged uses have been reassigned, **Remove unused version** removes
  the old product and moves its remaining favorite/meal-template references.
  The prior UI incorrectly registered checkbox validation on this form's hidden
  remove-id input, cancelling submission. It now uses a single confirmation.
- All sixteen tracked macros/micros default to numeric **0** on new saves and
  nutrition corrections when a field is missing, blank or marked unknown/null.
  Search, barcode and OCR entry forms start at zero for unreported nutrients.
  The UI labels zero as an **accounting assumption**, not evidence a manufacturer
  reported zero. Invalid numeric entries (negative, NaN, infinity, >100000)
  remain rejected.

## Existing saved-food data

The independent **tracker-food-zero641.py** maintenance CLI performs the
requested one-time retroactive normalization. By default it only previews
products that would change. With explicit `--execute` it creates and verifies
a consistent SQLite/uploads backup before any write, and updates legacy
`tracker_food_products.nutrients` JSON in one all-or-nothing transaction.
Missing or null entries, or the explicit strings "unknown", "null", "none",
"n/a", "not reported" or "?", become 0.0 for all sixteen keys. Previously
reported numerics and custom supplemental fields remain intact. Invalid
historic data aborts the whole transaction for manual review.

Perform the backfill *after* guarded code deployment and only using the
configured instance's data directory and environment. Run independently on
DEV and PROD so no data crosses between environments. The backup archive
location and product counts are printed, and rerunning is idempotent.

## Qualification

Run the focused API and legacy compatibility tests and the existing Chromium
module, plus the newly added safe migration tests. No schema migrations or
new unsafe POST routes are added. Browser qualification must remain isolated.
Production promotion still requires the full signed DEV qualification receipt,
the exact-commit main promotion and guarded PROD deployment.
