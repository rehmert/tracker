# Release 766: consolidated mobile UX, cooking, device imports and reporting

Baseline: verified PROD/DEV Release 765 (`8c67580611fd945d9ae83f8015f071a24ab6fee5`).
Release branch: `release/766-mobile-recipes-device-trends`. A single combined release covers phases 2–4.

## Mobile inventory and Rapid Gym

- Phone inventory gets expandable cards showing filtered vial summaries,
  availability, COA state and direct record edit link. First 50 sorted
  records appear in cards; original sortable/paginated table and bulk
  selection remain accessible via an explicit phone toggle.
- Next/previous machine navigation appears above Rapid Gym input, with a
  prompt before navigation only when unsaved values differ from initial
  fields. The on/offline indicator does not change existing offline queue
  behavior, record a set, or auto-finish workouts.

## Cooked recipe builder and data import

- Existing saved foods are used as recipe ingredients by **number of
  recorded servings**; the user enters actual total cooked batch mass.
  Recipe output is a new saved food with per-100-g cooked values.
- Ingredients missing a particular nutrient propagate an unknown result.
  Rebuild produces a NEW saved-food product to preserve historical logs,
  and deletion removes only recipe definition. Existing saved-food MACD
  continues to manage the generated product.
- Recipe metadata uses a separate additive table in the existing
  access-restricted Food database; users without Food permission are
  denied by the existing guard.
- Daily device imports accept up to 2,000 records / 256 KiB from UTF-8
  CSV with `date,steps,sleep_hours,resting_bpm,glucose_avg_mgdl`.
  Day ranges, finite values and source/date duplicate constraints are
  enforced before writing. Default is skip on collision, explicit Replace
  opts into overwrite. Manual add and delete are also supported.
  No API sync, raw CGM sensor records, or vendor-specific parsers are added.
- The only new workspace-scoped ORM table is `device_days766`, registered
  via Base metadata. No established table is altered.

## Integrated weekly trends

- Private read-only weekly report and CSV for 28, 90 or 180 days:
  actual daily weight/waist, completed workouts, logged doses,
  complete-protein nutrition days, and imported steps/sleep/resting
  pulse/glucose averages. Missing records stay unknown.
- Overlapping device sources use last nonempty metric per calendar day,
  without summing across devices. Days supporting averages are shown.
- No extrapolation, clinical score or implied causation. Existing
  Progress and Lab reports remain independent.

## Qualification, backups, release

- One isolated exact-target qualification with synthetic data, Jinja/Python
  and JS syntax checks, phone Chromium widths 360/430, Food/Workout/
  Progress/Today/scoped-db targeted regressions. No full test suite.
- The guarded DEV installer captures a verified private SQLite+attachment
  backup *before* installing the source that introduces the new table;
  retains at most 10 dedicated Release 766 snapshots.
- PROD is NOT authorized by DEV qualification or installation.
  A separate production preflight must review the additive schema and
  enforce existing database/attachment backup and rollback protocol.
  Never upload user data, secrets, archives or raw logs to GitHub.
