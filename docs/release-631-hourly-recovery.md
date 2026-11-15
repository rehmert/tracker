# Release 631 — Hourly Recovery Policy

## Schedule and retention

- Both Tracker hosts use `tracker-backup.timer` hourly with no randomized delay.
- Scheduled archives retain the newest 48 snapshots (approximately two days).
- Scheduled creation continues to verify archive integrity and perform an isolated restore before pruning.
- The operator-only `scripts/tracker-hourly-backup-policy631.sh` installs a pair of systemd drop-ins, without restarting Tracker, changing the database, or deleting existing backups.
- That installer fails closed if the canonical timer/service is absent, disabled, inactive, unexpectedly triggered, or a cron backup trigger is detected. Run with `--audit` to inspect and `--apply` to install. Execute separately on DEV and PROD.
- Setting `TRACKER_BACKUP_KEEP=48` on the service ExecStart environment ensures that existing environment files cannot override it with the former 90-archive default.
- Existing release backups under `/tmp/tracker-backups/` are **not** pruned by this policy. Those are on tmpfs and should be handled separately.

## Deployment database snapshots

- Ordinary code-only releases preserve a source/configuration snapshot and do **not** make an additional SQLite archive.
- Explicit data migration releases use `--db-migration`: they create a consistent SQLite + uploads backup and require isolated restore verification before installation.
- Recognized schema, dependency and systemd changes still fail closed in the standard release worker, requiring a separately reviewed migration/deployment procedure. A schema migration must include a verified backup in that reviewed process.
- Historical DEV qualification receipts with restore evidence remain valid. New receipts require exactly one of the verified-restore or explicit-no-migration-snapshot markers.
- PROD still requires signed exact-commit DEV approval and its own normal qualification gates.

## Validation

Run `bash -n` on the release worker and backup policy installer and targeted backend tests in an isolated candidate worktree before deploying Release 631. Full browser qualification is not needed for the timer-only host configuration change.

## Retention note

A rolling 48-hour window does not protect against corruption discovered after two days. Keep an independently managed daily or weekly off-host backup for longer-term disaster recovery.
