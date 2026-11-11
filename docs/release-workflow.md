# Tracker release workflow

> **Release 568 update:** DEV remains the deployment control point. First
> qualify the exact target with the guarded DEV runner and review it in the
> DEV browser. Then run `scripts/tracker_promote568.py` from DEV for signed
> promotion and remote guarded PROD deployment over SSH. The default is a
> non-deploying dry-run; `--execute` explicitly authorizes promotion.
> See [Release 568 operations workflow](release-568-ops-tooling.md).

> **Release 569 update:** The observed Python 3.13.5/SQLite 3.46.1
> dependency baseline is recorded for both hosts. Run
> `scripts/tracker_dependency_baseline569.py --instance DEV` locally on DEV,
> and the same script with `--instance PROD` over key-based SSH for
> read-only drift detection. It does not update installed packages or close
> the fresh-install qualification work in issue #10.
> See [Release 569 baseline](release-569-dependency-baseline.md).

> **Release 570 update:** After a tooling-only deployment, the
> operator may run `scripts/tracker_freshenv570.py` on DEV to replay
> the recorded package versions into a disposable new venv, fetch a
> separate Chromium and run isolated backend/browser QA. It is
> **dry-run by default** and never changes the installed venv.
> See [Release 570 disposable replay](release-570-disposable-replay.md).
> Full cross-host reproducibility remains subject to separate validation.

> **Release 571 update:** Once an isolated Release 570 replay is run
> with `--execute --retain-artifacts`, DEV may validate its wheel
> hashes and browser revisions, then preserve an independently verified,
> root-only recovery directory. Default mode does not write an archive.
> See [Release 571 recovery artifacts](release-571-recovery-artifacts.md).

Tracker DEV and PROD run the same Git history; local /etc/tracker.env has
TRACKER_INSTANCE=DEV or TRACKER_INSTANCE=PROD. No releases deploy themselves.

Once installed, use this single command instead of a new custom installer
for each release (as root on the target instance):

    bash /opt/tracker/scripts/tracker-release.sh --instance DEV \
      --base <installed-40-character-SHA> \
      --target <reviewed-40-character-SHA> \
      --ref release/reviewed-branch

The tool checks clean-tree status, local instance, pinned SHAs and ancestry;
fetches the exact ref; starts an independent systemd worker (currently capped at 6 GiB);
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


## Manual backup recovery checks

The Backups page now offers **Create and test backup** and
**Test latest backup restoration**. Both perform a full private temporary
restore via the same verification subprocess used by scheduled backups.
The latter only accepts the newest filename from the configured backup
directory, never a user-supplied filesystem path. Its receipt reflects
the newest backup, not an older archive.

These are explicit server-side actions. They may take longer for large
archives. An unsuccessful restore never writes a new success receipt,
does not delete the archive, and never prunes prior backups. A successful
manual creation updates the restore status immediately. The separate
"Verify now" button continues to check archive checksum/SQLite integrity
without claiming to perform an isolated restore.


## Secondary local backup integrity (optional)

The existing scripts/replicate_backups.sh entry point now invokes
scripts/tracker_replica.py, which uses only Python's standard library and
the existing Tracker ZIP verifier. The default directories are
/opt/tracker/backups (primary) and /tracker-backups (secondary);
override via TRACKER_BACKUP_DIR and TRACKER_BACKUP_REPLICA_DIR or use
--source/--dest on the Python command.

Replication confirms primary archive hashes match existing secondary
archives; new copies are checked for ZIP contents, SHA-256 and SQLite
integrity before being copied to a temporary file, rehashed and atomically
published. It refuses to overwrite a conflicting existing replica, avoids
source/destination symlinks and only prunes secondary archives after the
full selected set has matched successfully. A metadata-only receipt (mode 0644 so Tracker can read it when a root
account performs replication) in the secondary directory supports a lightweight
status row in Maintenance Review. The directory must be traversable by the
Tracker service account; the backup archives themselves can remain private.
That row uses metadata and is point-in-time evidence; it does not rehash
all backups during a page view.

Use this command on each host if /tracker-backups is available:

    bash /opt/tracker/scripts/replicate_backups.sh

A missing optional secondary directory is not an application failure.
A local or same-host secondary backup is **not off-site redundancy**.
Retain separate off-host copies, with their own restore checks.


## Backup storage headroom and secondary placement

The Backups page and Maintenance Review now show a **read-only** capacity
signal for the primary archive filesystem, including free space, number of
archives and aggregate ZIP size. The warning threshold is the larger of
512 MiB or three times the latest archive's compressed size. It is only
a heuristic, not a guarantee of enough space for snapshots, decompression,
or future uploads; no backup is blocked by this check.

If a secondary local directory is configured or present, the pages
compare filesystem device IDs and free capacity. A copy on the **same**
filesystem is labeled a shared-failure risk. A different filesystem
does not prove a different physical drive or off-site backup.
No automated secondary copying, scheduler, or retention behavior is
changed by this release.

## Faster dose logging and safe history reuse

A committed HTMX dose log response emits a one-use token in
HX-Trigger-After-Settle. The client renews the form token after the
existing reset handler and refreshes the local recording time. Failed,
invalid, and replayed submissions never rotate the token; durable
idempotency remains enforced by the server.

The dose History table includes Prepare similar for recorded
administrations (not waste). It opens a new GET-only form and prefills
the same vial, historical entered amount/unit and recorded site only
if the vial is still active and has sufficient remaining inventory.
It does not copy historical time, notes, disposable consumption or
one-use token, and never posts a dose. Calendar-planned handoff takes
priority over history prefill. Users explicitly review and submit.

Protocol editing has shortcuts to the protocol list, calendar and dose
log. There are no changes to dosing calculations, projections,
inventory mutation endpoints, or database schema.

## Protocol list next planned and vial handoff

The Protocols page shows the closest visible projected occurrence for each
active, dated protocol within 60 days, honoring saved escalation weeks,
weekly day selections, 84-hour schedule times and hidden projections. It
includes a Next planned first sort and a Choose vial shortcut. The shortcut
passes compound, date, time, amount and unit to the existing Dose Workspace;
it never logs a dose, chooses a physical vial or consumes inventory.

What-if protocols, missing start dates, ended plans and schedules without an
occurrence in the lookahead are labeled explicitly. This is calendar planning
information only; actual administrations are not reconciled in the index.

## Protocol inventory handoff and planned-date date warnings

The Protocols page now reports a conservative, read-only inventory check beside
its next visible planned occurrence. It compares each active vial's recorded
remaining quantity to that event in compatible units and excludes candidates
with recorded expiration or beyond-use dates reached by the planned day. It
reports missing stock, insufficient single-vial quantity, unit/concentration
incompatibility, or recorded date warnings instead of guessing.

When a matching candidate exists, Review suggested vial opens the normal
/doses form with that vial and the plan's context prefilled; all entry fields
must still be confirmed and the normal dose write validation remains in place.
The existing Choose vial link continues to open Dose Workspace. Dose Workspace
now checks recorded vial dates against the planned date when one is supplied,
instead of only today. This is not a sterility or clinical judgment, and
future availability can change. No dosing, inventory or schema writes added.
