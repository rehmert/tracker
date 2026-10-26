# Tracker — Phases 1–3 update (2.0.0)

Base: `tracker-dashboard-order-fix.zip`. The application retains the existing Soft Modern appearance, density selector, and previous releases.

## Phase 1 — accuracy and reliability
- Dose edit form now shows original disposable selections; changing them restores old consumption and applies corrected consumption in one database transaction. An audit snapshot records original and corrected amounts/usage.
- Filtering/preparation records now have an edit screen for dates, notes, and disposable usage. Filtering records can be deleted and their associated supplies restored. Reconstitution event deletion is deliberately blocked because it can invalidate vial volume and historical dosing; edit vial details to correct the recorded liquid volume.
- Inventory reconciliation (`/reconciliation`) accepts physical counts and required explanations, without changing purchase records or historical usage. Every adjustment is logged.
- Data integrity (`/data-integrity`) flags negative supply quantities, negative purchases, missing supply names, active expired vials, future reconstitution dates, and nonpositive dose amounts. This is a limited set of checks, not a comprehensive validation engine.
- Change audit covers edited doses, preparation corrections/deletions, and supply reconciliations; it is not a universal audit trail for all record types.

## Phase 2 — usability and analytics
- `/quick-entry` offers mobile-friendly navigation to dose, vitals, supply-use, and vial preparation entry.
- `/consumption` shows per-supply usage over selectable periods and simple historical coverage estimates.
- Existing dashboard personalization, Ctrl+K search, filters, and responsive styles remain.
- A dedicated offline-capable PWA, fully redesigned mobile entry forms, and additional dashboard widgets are **not** part of this update.

## Phase 3 — maintainability
- Protocol save/status/date operations append snapshots viewable at `/protocols/{id}/history`. Earlier protocol changes cannot be reconstructed.
- Sidebar shows application version and links to `/release-info`.
- Startup records `tracker_phases_1_3_v2` in `tracker_schema_migrations` and creates new additive tables with SQLAlchemy `create_all`.
- This does **not** replace existing startup migrations with Alembic; adopting Alembic safely requires a separately tested schema baseline and migration chain.

## Installation
1. Use Tracker's Backups page to create and verify a backup; preserve database, `.env`, `data/`, and uploads.
2. Deploy application files from this ZIP over the current application.
3. Restart: `sudo systemctl restart tracker.service`.
4. Hard-refresh Chrome with Ctrl+Shift+R.

New tables: `inventory_adjustments`, `change_audit`, `protocol_revisions`. Existing data is retained. There are no destructive schema changes.

## Validation
`python -m pytest -q`: 91 passed (87 existing plus 4 new tests). This does not replace testing against a copy of your production database, especially the historical COA and preparation data.
