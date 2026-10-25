# COA relationship repair

This update uses `vials.coa_id -> coas.id` exclusively. One COA can be assigned to many vials; each vial has at most one COA.

## Deploy

1. **Back up your SQLite database and uploads first** (use `scripts/backup.sh` or a filesystem snapshot).
2. Stop the Tracker service and copy this application over your existing application code, preserving your `data/` directory and `.env` settings.
3. Ensure SQLite is version 3.35+ (`python -c "import sqlite3; print(sqlite3.sqlite_version)"`); the migration uses `ALTER TABLE ... DROP COLUMN`.
4. Start Tracker. The lifespan migration automatically adds `vials.coa_id`, transfers legacy `coas.vial_id` and `coa_vials` associations, then removes those legacy schema elements.
5. Verify `/vials`, `/coas`, and a vial detail page. Run `python -m pytest -q` in a test environment.

**Important:** If a vial has conflicting or multiple legacy COAs, the migration stops with a clear error rather than silently discarding assignments. Resolve the conflicting associations on a copy of your database first. Do not drop old tables manually before migration.

## Changes

- Fixed routes, services, templates and dashboard still using removed `.coas`, `.linked_coas`, `.linked_vials`, `.vial_id` relationships.
- COA upload now sets `vial.coa_id` and bulk assignment sets the same FK.
- COA deletion clears linked vial foreign keys via `ON DELETE SET NULL` and only removes uploaded files after database commit.
- Existing COA references are migrated on startup, including the old `coa_vials` association table.
- Fixed an existing vitals test assumption: configured display units default to pounds, not kilograms.

Do not use the `schema.sql` script to recreate your production database. SQLAlchemy and the additive migration handle existing databases.
