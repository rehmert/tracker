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
