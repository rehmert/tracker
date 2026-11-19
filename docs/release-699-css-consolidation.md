# Release 699 — Density CSS consolidation, no visual changes

Baseline: Release 698 deployed successfully on DEV and PROD,
`a280455fe031c8aa634b84128bab81569d075779`.
Candidate branch: `release/699-css-consolidation`.

## Scope

A small, controlled first pass toward CSS consolidation. The existing
Release 685 and 686 density stylesheets change, and their versioned stylesheet
URLs in `base.html` are refreshed to prevent stale browser caching. No other
application assets, page structure, server code, database schema, user data,
forms or routes are touched.

**Release 685:**
- Factor repeated compact dashboard/page-header selectors using
  `:is(.dashboard-hero,.page-header)` while preserving CSS specificity,
  declarations and original rules' position.
- Factor duplicate section-intro/panel-heading heading selectors.
- Consolidate the duplicate compact card padding declarations into the
  later all-card rule, keeping balanced cards in their independent rule.

**Release 686:**
- Remove `.tracker-ui-action` and `.ux673-action-row` from the mobile
  `min-height: 44px` list; they already receive the same value from
  the earlier Release 685 mobile rule, which remains intact.
- Keep all additional Daily-specific 44px targets in Release 686.

This is an intentional minimal-risk improvement, **not** a wholesale
deletion of older stylesheets or a shared component rewrite. Release 700
can continue only after this step is visually qualified and deployed.

## Why the test gate is stricter than Release 698 alone

Release 698 compares 136 real-page screenshots at four widths and two themes,
using isolated empty-data DEV instances. Its real-page comparison does **not**
explicitly cycle through all Tracker density preferences. For this CSS
refactor, `tests/browser/test_css_parity699.py` additionally renders
identical original and candidate CSS against a static, representative set of
Dashboard, forms, cards, toolbar, Workout and Daily selectors in Chromium.

- 5 widths: 320, 390, 768, 1280 and 1920px
- 3 densities: compact, balanced and comfortable
- 2 themes: light and dark
- 2 stylesheet modes: standalone 685, and 685 plus 686
- **60 strict comparisons**, requiring identical computed styles,
  element positions/sizes and zero screenshot pixel differences

The normal 136-comparison real-page visual gate is then run **unchanged**
against the pinned Release 698 source and current candidate. Browser routes
are limited to two loopback origins; each side has its own separate disposable
SQLite data directory. No installed user data or screenshots are published.
A visual failure blocks the release, preserving only private diff evidence.

## Qualification, recovery and scope

`scripts/tracker-release-scoped699.sh` checks CSS/Jinja syntax, exact
source contracts, historical Release 685 and Release 686 density tests, and
scoped Release 679/688/690 source tests. Full application regression
suites are not requested. This runs in an isolated worktree on DEV.

`scripts/tracker-preview699.sh` verifies the exact installed baseline,
the candidate ref, and an **eight-file allowlist**. It first runs scoped
source checks, then strict three-density CSS parity, then the existing
dual-isolated-server Release 698 visual comparisons. There are no downloads,
installed-app mutations, main-branch changes or production operations.

A successful preview is the qualification prerequisite for the guarded
DEV install; only after DEV verification and review can the usual
signed DEV-controlled PROD promotion run. This document does not assert
that the executable tests have run.
