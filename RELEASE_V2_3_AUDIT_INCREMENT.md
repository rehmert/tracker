# Tracker v2.3 — Administration audit increment

Built on the user-supplied updated Tracker source plus the v2.3 PK comparison CSV increment.

## Changes
- Editing an administration now stores complete before/after snapshots: vial, timestamp, entered amount/unit, normalized amount, kind, site, notes, and supply consumption.
- Deleting an administration writes a durable audit record before restoring supply usage and deleting the entry.
- The administration edit page shows a correction-history table.
- Adds a regression test for edit history and deletion auditing.

## Validation
`PYTHONPATH=. python -m pytest -q` — **97 passed**.

## Deployment
Review/commit the changed application files through Git; do not overwrite live `.env`, `data/`, `backups/`, or `/tracker-backups/`. No database migration is required because the existing `change_audit` table is reused.

## Scope
This is an incremental release, not a full audit viewer or undo capability. Existing records deleted before this update cannot be reconstructed from the new audit trail.
