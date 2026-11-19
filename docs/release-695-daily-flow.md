# Release 695 — Daily workflow consolidation (first scoped pass)

Baseline: Release 694, exact deployed PROD and DEV commit
`6a44ab33176cc6586066e0621774e539049ff338`.
Branch: `release/695-daily-flow`.

## User-visible behavior

- **Today** (`/mobile`) now places the existing schedule-status count before one
  primary seven-destination recording strip: Vitals, Dose, Food, Water, Workout
  Set (Gym Mode), Supplements/Meds (Regimen), and All Actions (Quick Entry).
  Nothing here records an administration or measurement until the existing
  form is submitted.
- The Daily Command Center still shows the existing food, calories, sets and
  vial-date summaries. Its duplicate Food, Workout, and Vitals action row is
  removed; instead, concise **review links** are in the appropriate summary
  cards. Last Workout remains conditional, with a Workout History fallback.
- **Quick Entry** (`/quick-entry`) retains all existing fast links, searchable
  cards and category filters. Adds Workout Set and Supplements/Meds to the
  searchable *Daily* and *Record* categories, so the complete action directory
  matches Today. Existing links continue to work.
- **Overview** remains the desktop-wide reporting dashboard, and **Calendar**
  remains the schedule review. Neither was redesigned or re-routed.

## Scope and safety

Template/CSS changes only to existing Today and Quick Entry pages.
No changes to authentication, CSRF, underlying FastAPI routes, models,
SQLite schema, saving behavior, data queries or production data.
Links always navigate to existing record/review forms. The embedded Today
Vitals POST form and safeguards are left untouched. The summary remains
read-only and respects the existing Food availability presentation.

## Qualification and release procedure

`scripts/tracker-preview695.sh` requires the exact Release 694 baseline
installed on `tracker-dev`, a clean repository, and a root systemd worker.
It creates a detached candidate worktree and disposable SQLite data directory,
runs the release-specific focused source tests via
`scripts/tracker-release-scoped695.sh`, and launches a loopback-only
candidate for Chromium checks at 320, 390, 768 and 1280 px. The browser
checks enforce accessible one-tap destinations, layout without horizontal
overflow, and newly searchable actions. No full regression suite, downloads,
or PROD deployment.

After exact-commit isolated preview passes, use the existing guarded
`scripts/tracker-release.sh --instance DEV` (no full-suite override),
then visually approve DEV before the signed DEV-controlled PROD promotion.
Never promote on preliminary preview results alone.
