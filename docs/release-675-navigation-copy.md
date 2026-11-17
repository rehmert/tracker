# Release 675 — Mobile Navigation and Copy Cleanup

Baseline: Release 674, `18cc2944a6ed747eede74c040f2ed622eaa3477c`.
Candidate: `release/675-navigation-copy-polish`.

## Scope

One integrated, code-only interface release targeting raw navigation links,
crowded mobile action rows and unnecessarily long explanatory copy.

- **Workouts main**: clear Gym Mode, Progress, Calendar actions and a More
  disclosure for backfill, Insights and Routines. Preserves the same URLs and
  the complete set-entry, session, QR mapping, and routine workflows.
- **Rapid Gym**: concise navigation, compact routine tools and shorter load,
  planned-order and offline-draft descriptions; important "not logged"
  semantics retained. No changes to saved sets, progression, or offline sync.
- **Workout review**: All Sets, Corrections, and a More menu for CSV exports,
  Progress, Insights and Calendar. Both CSV export variants remain distinct.
- **Workout analytics, calendar and program**: touch-friendly navigation,
  concise headings and explanations, without altering training calculations.
- **Quick Entry**: shortened quick-action labels and all action-card
  descriptions. Existing 15 quick shortcuts, search, category filter and
  original destinations are preserved. "BP" retains accessible full name.
- **Purchases**: main actions and secondary More menu, compact order workflow
  steps, clearer stock/cost warnings. All filtering, CSV, item-add and
  purchasing endpoints remain untouched.

The new shared `tracker-action-nav675.css` provides reusable GET-link
styling, minimum 44-pixel touch targets, keyboard-visible focus, a flexible
More disclosure and two-column or one-column small-phone layouts.

## What is not changed

- Database schema, migrations, API route handlers, stored records, or
  calculations.
- CSRF, authentication, security or shared backend infrastructure.
- Form methods, submission endpoints, or inventory/Workout transaction flows.
- No full app-wide test suite is part of each release qualification.

## Qualification

`scripts/tracker-preview675.sh` uses a temporary isolated worktree with
no installation or PROD changes. `scripts/tracker-release-scoped675.sh`
runs syntax/Jinja checks, focused source and existing Workout/Purchase tests,
and disposable Chromium checks at widths 320, 375, 390, 430 and 768 px.
Chromium verifies no horizontal overflow in the changed navigation pattern,
minimum touch heights, and More disclosure interaction.

The guarded DEV-to-PROD path uses the same change-scoped gate. Readiness
requires explicit isolated preview qualification and a later approval marker.
