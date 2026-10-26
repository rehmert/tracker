# COA startup migration repair (2026-10-26)

This release fixes a startup failure caused by `ALTER TABLE coas DROP COLUMN vial_id` on existing SQLite databases.

## Deployment

1. Stop Tracker and make a **backup of the live SQLite database** (and the `data/uploads` directory). If the database is in WAL mode, stop the application before copying it, or use SQLite's `.backup` command.
2. Replace the application code with this ZIP; **preserve your `data/` directory and `.env`**.
3. Restart the Tracker service and check `journalctl -u tracker.service -n 100 --no-pager`.
4. Verify `/vials`, `/coas`, a vial detail page, and COA bulk assignment.

## Behavior

- The authoritative COA assignment is `vials.coa_id`.
- On first startup, legacy assignments from `coa_vials` and `coas.vial_id` are copied into `vials.coa_id` if they do not conflict.
- The old `coas.vial_id` column and `coa_vials` table are intentionally **not dropped**; they remain unused historical database objects. Removing them requires a separately planned SQLite table-rebuild migration.
- A `tracker_schema_migrations` marker prevents re-importing legacy associations after an assignment is edited or cleared.
- Conflicting legacy COAs raise an explanatory error rather than discarding associations.

## Validation

`python -m pytest -q` (40 passing tests, including legacy-schema migration regression tests).

Tests cannot guarantee compatibility with your specific production database. If startup still fails, provide the complete traceback and a redacted `.schema coas` / `.schema vials` output.
