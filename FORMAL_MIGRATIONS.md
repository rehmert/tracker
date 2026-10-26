# Tracker: formal schema migration foundation

Tracker now includes Alembic revision tracking (`alembic_version`), an initial
non-destructive adoption revision, and a repeatable upgrade command.

## First deployment (stop the app first)

1. Create and **verify** a backup using the existing Backups page, including uploads.
2. Stop the service: `sudo systemctl stop tracker.service`.
3. Deploy the new code while **preserving** `.env`, `data/`, and uploads.
4. In the Tracker virtual environment, run `pip install -r requirements.txt`.
5. From the project root, run `./scripts/tracker-db-upgrade.sh`.
6. Verify `python -m alembic current` shows `20261026_01 (head)`.
7. Restart: `sudo systemctl start tracker.service`.

The first revision supports both fresh installations and databases created by
previous Tracker releases. It calls the existing additive migration functions
and creates missing tables; it does not drop legacy COA structures.

## Future changes

Use `python -m alembic revision -m 'description'` and implement explicit
`upgrade()` operations. Review the generated SQL and test against a copy of
production data before deploying. Do **not** blindly autogenerate destructive
operations against legacy databases. `python -m alembic history` shows revisions.

## Transitional compatibility

For backward compatibility, the app's startup still runs its existing
idempotent additive migration routine. Alembic now provides a formal revision
history and a controlled pre-start upgrade path, but the old startup mechanism
has **not** been removed yet. Future schema changes should be authored as
Alembic revisions and deployed with the command above. Existing installations
will not be automatically stamped until the upgrade command is run.

Rollback is by restoring a verified backup (database **and** uploads), not by
running destructive Alembic downgrades.
