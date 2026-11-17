# Release 672 — Saved Food Editing and Action-Control Consistency

Baseline: Release 671 at `b12d85fffcd1840a5029881fb14fe86f572b20f4`.
Branch: `release/672-food-edit-ux-cleanup`.

## Requested saved-food behavior

The Food Journal saved-food editor no longer has an acknowledgement checkbox
and the POST handler no longer rejects an update for lack of confirmation.
Clicking **Save Food Changes** saves the edited record following existing
field validation and optimistic stale-version checks. The informational note
about updating historical journal totals remains, but is never an extra gate.

## Cross-application link/button audit

Searched action-labeled anchor usages, including Edit, Cancel, Save, Delete,
Remove, Manage and action links rendered next to form buttons. Distinguished
navigation and references from controls occupying action rows.

Corrected:
- Food Editor: Cancel now has the standard outlined button appearance.
- Compounds editor, Notes editor, Labs editor, Vendor Price editor and
  Workout backfill: Cancel next to Save is consistently button-styled, while
  preserving normal link navigation semantics.
- Compounds table and Purchase Details: Edit beside Delete is now an actual
  GET-form button; Delete is an actual button with red text.
- Vendor Price offers: replaced bespoke Edit anchor with actual GET-form
  button beside Delete, retaining the editor fragment destination.
- Vitals readings: replaced Edit anchor with GET-form button preserving
  `days` and `events` query inputs, and made HTMX Delete visually
  consistent while retaining the original endpoint and confirmation.

Preserved intentionally:
- Breadcrumbs, date navigation, notes links, inline pricing references,
  drill-down links and other actual navigation content are links.
- Account Management's standalone Edit link occurs in a security-sensitive
  route and was not altered; changing that module requires separate
  security-focused qualification.
- Existing explicitly button-styled navigation actions were not rewritten
  indiscriminately.

This audit is based on repository code-search results and the inspected
templates, not a browser-by-browser visual acceptance claim. The tests provide
source-level contracts and existing focused API regressions.

No schema, permission, authentication, request origin, dependency or
shared authorization changes are included. No migration required.
The readiness marker `docs/release-672-ready.txt` is added only after an
isolated DEV preview passes.

## Qualification

`scripts/tracker-preview672.sh` checks an isolated source checkout without
installing it, and executes `scripts/tracker-release-scoped672.sh`.
The focused suite covers saved-food validation and journal totals, all
saved-food action buttons, adjusted Cancel/Edit/Delete markup, vendor, vitals,
and selected Workout regression tests.

Signed DEV-to-PROD deployment uses `scripts/tracker-release672.sh` only after
explicit readiness approval, and repeats focused tests on PROD before install.
No GitHub Actions and no full application regression suite.
