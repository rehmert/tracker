# Release 629 — Saved Food Duplicate Review and Safe Consolidation

## Purpose

Prioritize saved-food cleanup before further PK Simulator enhancements.
Adds a dedicated Food Journal link to **Review Duplicates**, serving the
authenticated `/food/duplicates` page.

## Review experience

- Group products with the same normalized name (whitespace/case-insensitive).
- Show every candidate product ID, serving description, barcode, source,
  logged meal count, meal-template references and favorite status.
- Compare every supported macro- and micronutrient per stored serving
  in a side-by-side table.
- Display absent nutrients as **unknown**, never zero.
- Distinguish matching names with differing serving sizes, barcodes or
  nutrient values; these are **review only**, not automatically merged.
- For fully equivalent versions, choose a canonical product and explicitly
  select versions to remove. A browser confirmation explains the action.
  A server-side validation independently rejects incompatible records.

## Transactional behavior

All consolidation changes happen within one SQLAlchemy transaction:
move food-log references, move meal-template product references,
preserve the favorite state, and remove the redundant product.
No calories or micronutrient values are recalculated. Existing
historical food logs remain in place, pointing to the retained
nutrient-equivalent product. Other distinct versions remain untouched.

The backend refuses duplicate IDs, invalid form fields, cross-group
mismatches, different serving/barcode/nutrient payloads, and stale
missing product IDs. Access uses the existing administrator food
storage guard, request-authorized engine and browser CSRF form
token mechanism. No automatic merge occurs on page load.

## No unknown nutrients in new entries or corrections

Following the additional requirement, new Food Journal entries and
copy-on-write nutrition corrections must provide all 16 supported
macro- and micronutrient values, as explicit finite nonnegative
numbers. Empty fields and the string "unknown" result in HTTP 422
before a food product or journal entry is written. A confirmed
numeric zero remains allowed; unknown **must not** be silently
converted to zero.

Both forms mark nutrient inputs as required, keep the micronutrient
sections open for browser validity feedback, and report the missing
fields in the nutrition review. Barcode/OCR imports can supply a
partial prefilling but cannot save until complete. Historical saved
foods containing missing nutrients remain readable and comparable;
the migration does not rewrite their nutrient values. Other
optional targets and secondary-user food workflows are not changed.

The focused gate runs `tests/test_release629_required_nutrients.py`
for complete entries, rejected blanks/nonnumeric values, zero,
and atomic failed corrections. Older tests specifically designed to
allow incomplete foods will be updated during the next full
checkpoint (Release 630), not run as a routine release gate.

## Data boundaries

The assistant has no live access to the user's saved foods. Therefore
the number of duplicate groups and their actual nutrient values can
only appear in the authenticated Tracker review page after deployment,
not in this chat. This first pass addresses the administrator Food
Journal product library, not separate secondary-user workspaces.
The review scans up to 5,000 products and clearly warns if truncated.
Same-name but nutrient-different versions must be reviewed separately;
they are not safely merged with historical logs without changing
historical nutrition values.

## Qualification

- `tests/test_release629_food_duplicates.py`: isolated SQLite tests
  for supported nutrient values, unknown-vs-zero, equivalence,
  transactional log/template/favorite preservation and rejection of
  incompatible choices, plus an isolated HTTP GET/POST route exercise.
- `scripts/tracker-focused-regression604.sh`: 16-worker focused gate
  includes the new tests and relevant existing food journaling
  contracts, not the large historical CSRF suite.
- Source compilation, Jinja parse, static change impact, exact SHA
  pinning, verified backup/restore, runtime smoke and rollback remain
  mandatory. Full backend and Chromium qualification is scheduled for
  Release 630, or an actual authentication/CSRF change.

Deployment requires confirming the installed Release 628 SHA
`ad80ae2d2a46be1fbb977347606f98fd76e0f2da`.
PROD remains unchanged.
