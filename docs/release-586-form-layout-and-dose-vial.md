# Release 586 — form overlap protections and vial identity in dose log

**Base:** PROD Release 585 commit `cfc45002a9f2f33a8c2b89d2de854fd1019d0c9b`.

## Changes

- The Dose Log history table now includes a separate **Vial** column,
  linking to the actual source vial with its permanent #ID, optional
  user label and lot identifier.
- Dose Edit's **When** field now spans the full form grid. The existing
  24-hour date/time enhancer receives responsive Date, Time and
  Use current time control placement without covering neighboring fields.
- A shared, late-loaded style sheet protects form-grid and label controls
  throughout Tracker from intrinsic minimum-width overflow, including
  narrower mobile layouts and longer select options.
- Intentional table horizontal scrolling remains in place, rather than
  hiding or clipping long inventory tables.

## Layout audit and testing

The change targets shared form controls, not an isolated one-off date
input. A new isolated Playwright module navigates 20 real
form-heavy pages under disposable QA and checks field containment at
desktop, tablet and mobile widths:

`/doses`, `/vials`, `/purchases`, `/supplies`,
`/compounds`, `/vitals`, `/labs`, `/protocols`,
`/dose-workspace`, `/calendar`, `/food`, `/blends`, `/quick-entry`,
`/protocol-tools`, `/pages`, `/inventory-health`, `/inventory-alerts`,
`/reconciliation`, `/vendor-prices`, and `/health-timeline`.

An independently seeded, synthetic Dose Edit screen is checked at
1440, 800, 390 and 320 pixels, including rendered date/time-control
rectangles. The same module checks that the dose-history Vial link
matches the recorded DoseLog vial. Backend contracts cover the shared
stylesheet, the template cells/colspan, the responsive time-field
change, and full Chromium qualification registration.

**Limit:** Source inspection and selected-route Chromium checks are
not a proof that every viewport and every dynamic/custom browser state
of the entire application is overlap-free. Any regression flagged by
the expanded browser suite must be fixed before promotion.

## Safeguards

No schema or dependency changes. No alteration to dose inventory
accounting or submission logic. Global installed strict-CSRF remains
report-only. This release is not an authorization to deploy. Use exact
DEV qualification, visual review, dry-run PROD promotion, then explicit
DEV-controlled operator promotion.

The combined strict-CSRF coverage/readiness work is now planned after
this intervening feature as **Release 587–588** (one bundled promotion);
Issue #9 remains open.
