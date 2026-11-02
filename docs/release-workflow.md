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
