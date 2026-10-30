# Tracker usability release — 2026-10-30

This is an incremental UI patch, not a complete implementation of the full four-release roadmap.

## Included
- Correct invalid Calendar title block; preserve existing hidden-projection manager in page body.
- Improve Calendar status legend and matching language.
- Add a global + Add quick-action menu.
- Add breadcrumbs to detail routes without changing URLs.
- Clarify active versus hypothetical protocols, recorded versus planned doses, purchase header versus items, and vial inventory versus compound definitions.
- Add contextual cross-page workflow links for protocols, doses, purchases, vials, inventory and vendor pricing.
- Clarify blend preview versus inventory-changing submit.
- Remove redundant visible PK graph button while preserving its DOM for existing JavaScript.
- Remove hard-coded 2.0.0 release heading.
- Add reusable theme-aware styling and sticky table headings.

## Deferred / requires backend and integration work
- Fully consolidated Inventory Health route and redirects; audit history and record change logs.
- Full global search extension to data actions; saved server-side views.
- True multistep purchase, blend, and protocol wizards.
- Reliable verified backup/restore checks and full-dataset export.
- Broad automated browser and database integration testing.

No schema changes. No production data included. Back up /opt/tracker/data and uploads before deployment.
