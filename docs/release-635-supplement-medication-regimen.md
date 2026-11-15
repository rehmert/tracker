# Release 635 — Supplements & Medications

## Scope

Adds a first-class **Supplements & Medications** page at `/regimen`, linked from the sidebar, Food Journal and mobile Today page.

- Catalog distinguishes **supplement** from **medication**, with name, ingredient, strength, formulation, user-entered instructions, purpose, optional prescriber, notes and archival status.
- Independent schedules support **daily**, **specific weekdays**, **every N days**, and **as needed (PRN)**. Planned amounts are user-entered and are not medication recommendations. Every-N-days schedules are anchored to their start date. Weekly days are 0=Monday through 6=Sunday.
- Daily view shows due scheduled items, actual status, date navigation, and shortcuts to Food Journal and injectable doses. PRN products do not appear as automatically due.
- A separate manual intake form logs both scheduled and unscheduled intake, with timestamp, outcome (**taken/skipped**), exact user-entered amount, optional meal association and notes. One scheduled intake per schedule/date is allowed to prevent accidental duplicate submissions; unscheduled logs can occur more often.
- Edit/delete intake, edit/archive catalog item, edit/stop schedules. Historical intake remains when schedules stop or catalog items are archived. All writes are audited with before/after records.
- No auto-population from the user's medication history, no automatic clinical prescriptions, and no integration with the food nutrient totals. Do not enter private data as test fixtures.

## Schema and isolation

Additive SQLAlchemy tables:
`regimen_items635`, `regimen_schedules635`, `regimen_entries635`.
The existing startup `Base.metadata.create_all(engine)` creates new tables on application startup; no destructive schema alteration of existing tables.
Authorized legacy-admin workspace sessions are supplied by `get_scoped_db390`. The new router uses the existing database-write reservation and `ChangeAudit`. Food Journal SQLite tables, vial/dose tables and existing protocols are not mutated.

## Out of scope / intentionally deferred

Research references and evidence grading, automatic medication interaction checks, refill inventory and forecasting, per-ingredient verified nutrients and automatic nutrition attribution, importing existing injections as new oral regimen entries. These require distinct data integrity and clinical-data designs; do not silently provide them in this release.

## DEV qualification

Run in the existing isolated candidate worktree using the existing DEV test environment:

```bash
/opt/tracker/.venv/bin/python -m pytest -q --tb=short --maxfail=1 \
  tests/test_release635_regimen.py \
  tests/test_bulk_vial_transactions.py \
  tests/test_release634_vial_compound.py
```

Use the established guarded DEV release workflow, not direct edits to deployed source. Inspect `/regimen` and run browser QA under both ordinary and strict configured security modes before a signed PROD promotion. PROD remains on the previous release until approved.

## Manual validation

1. Add a supplement and medication; confirm their own catalog cards.
2. Create daily, weekday, every-N-day and PRN schedules; navigate across dates and confirm PRN never shows as due.
3. Record taken and skipped, edit a mistaken amount/meal and verify changes.
4. Archive and stop schedules; verify historical records remain.
5. Open Food Journal: nutrient totals must not change from recording medications or supplements alone.
6. Inspect mobile Today shortcut and responsive layout.


## Explicit reviewed-schema deployment exception

The ordinary release runner deliberately refuses modifications to `app/models.py`. Release 635 adds only three new tables, but it still requires explicit reviewed migration flags, not a silent relaxation of the guard.

On **DEV**, after isolated candidate testing, invoke the exact candidate runner with
`--reviewed-regimen-635 --db-migration`. Both flags are required. The
`tracker_schema_review635.py` step confirms all changed paths are on the
explicit Release 635 allowlist, existing model text is byte-for-byte
unchanged, and exactly the three expected model classes/tables were appended.
It does not permit modifications to database configuration, existing
migrations, dependencies, or systemd units.

The existing guarded worker then runs Release 635's full backend and isolated
browser qualification, snapshots configuration/source, obtains a full live
SQLite backup, verifies its isolated restore, and only then fast-forwards
the installed source and restarts the service.

The signed remote PROD deployment script passes the reviewed flags **only for
release number 635**. The existing signed exact-commit DEV approval, main
promotion, backup, full PROD regression gate, and runtime smoke checks remain
required. Do not run ordinary 635 promotion before the special DEV run
has completed with `DATABASE_BACKUP=VERIFIED_FOR_MIGRATION`.

This procedure does not automatically undo newly added SQLite tables on
rollback. The additive tables will be ignored by Release 634 code. Preserve
the verified pre-migration database archive for an explicit data-restoration
decision if needed. Never blindly overwrite a live database.
