# Tracker release workflow

Tracker DEV and PROD run the same Git history; local /etc/tracker.env has
TRACKER_INSTANCE=DEV or TRACKER_INSTANCE=PROD. No releases deploy themselves.

Once installed, use this single command instead of a new custom installer
for each release (as root on the target instance):

    bash /opt/tracker/scripts/tracker-release.sh --instance DEV \
      --base <installed-40-character-SHA> \
      --target <reviewed-40-character-SHA> \
      --ref release/reviewed-branch

The tool checks clean-tree status, local instance, pinned SHAs and ancestry;
fetches the exact ref; starts an independent, 1-GiB-capped systemd worker;
compiles and tests an isolated checkout against a disposable SQLite database;
takes private source/config and verified SQLite+uploads backups; performs an
isolated restore simulation; checks the application service account's file
access; fast-forwards code; and verifies /healthz and every sidebar page with
local credentials. Changes under app/ restart Tracker; tooling-only changes
do not. Failed post-install checks attempt a *code-only* rollback.

The release command now streams its complete log by default and returns a failure
status when the worker reports failure. It automatically stops following when
the worker exits. Press Ctrl+C to stop watching; the systemd worker continues.
Add `--detach` to return immediately and print the logfile path instead.

The log must report TRACKER RELEASE DEPLOYMENT SUCCESS and EXIT_STATUS=0.
Do not promote to PROD on a partial or failed log.

After a successful DEV deployment and browser review, fast-forward GitHub
main to the exact tested SHA (do not force push). On PROD use:

    bash /opt/tracker/scripts/tracker-release.sh --instance PROD \
      --base <current-PROD-40-character-SHA> \
      --target <promoted-40-character-SHA> \
      --ref main

PROD refuses to install an unpromoted release ref.

Database migrations, dependency changes and systemd unit changes are
deliberately blocked by this standard flow and need a separately reviewed
migration procedure.

Private release logs and backups are under /tmp/tracker-backups/release.*/.
Move copies of important backups off-host; /tmp is not durable storage.

## Restore validation

To test an existing full Tracker backup without touching the live database
or uploads:

    cd /opt/tracker
    .venv/bin/python scripts/tracker-restore-verify.py \
      --archive /path/to/tracker-2026...zip

It validates archive paths, checksums, SQLite integrity, uploaded file
hashes and foreign keys in a private temporary extraction that is removed
automatically. This is a non-destructive validation, not a complete
interactive disaster-recovery exercise.

## Recovery evidence on the Backups and Maintenance Review pages

The existing nightly tracker-backup.service invokes
python -m scripts.tracker_backup create. It now performs an **isolated**
SQLite-and-uploads restore check after creating each archive and before
pruning older backups. If the restore check fails, the command exits
nonzero; it retains the created archive and does not write a success
receipt or prune backups.

After a successful check, a private atomic
.tracker-restore-receipt.json is written in TRACKER_BACKUP_DIR
(default /opt/tracker/backups). It records the archive name, time, size,
modification time, SHA-256 and restored-data counts. The UI uses lightweight
metadata checks, not expensive ZIP hashing on each page view.
A new/changed archive, an old test (24+ hours), or a missing receipt
produces an attention status. This is point-in-time evidence, not
continual assurance of unchanged bytes or whole-host recoverability.

Run this to record a dry-run receipt for an existing configured backup:

    cd /opt/tracker
    .venv/bin/python scripts/tracker-restore-verify.py \
      --archive /opt/tracker/backups/tracker-EXAMPLE.zip \
      --record-status

Without --record-status, the isolated restoration remains read-only.
Archive verification in the Backups UI does not claim to be a restore.
Store an off-host copy and periodically rehearse whole-host recovery.
