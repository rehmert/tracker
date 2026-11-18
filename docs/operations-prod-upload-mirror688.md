# DEV upload mirroring (PROD → DEV)

Tracker's existing `scripts/tracker-prod-uploads-to-dev645.sh` is the authoritative
**additive-only** upload pull. The `tracker-prod-uploads-to-dev.timer` schedules
it every minute on `tracker-dev`.

## Scope and safety

- Source: `root@tracker-prod`, discovered from PROD's own `TRACKER_DATA_DIR`.
- Destination: DEV's canonical `/opt/tracker/data/uploads/`.
- Copied: upload file trees (including COA and lab attachments).
- Not copied: SQLite database, software, deployment state, or configuration.
- No deletions, no overwrite of existing DEV files.
- PROD only serves reads. Destination is always DEV.
- Retains the existing DEV/PROD identity checks, `tracker-db-sync.lock`
  and post-transfer SQLite attachment integrity scan.
- systemd imposes 512 MiB/96-task limits, a 15-minute timeout,
  and a read-only filesystem except for DEV uploads and the lock.
- Runs as a systemd oneshot unit; systemd never starts overlapping instances
  of the same service. A busy deployment lock causes a failed run that the
  next minute's calendar tick can retry.
- Uploaded documents may contain personal information. DEV must have access
  controls comparable to PROD before enabling the mirror.

## Installation

From a root shell on `tracker-dev`, use the pinned ops installation wrapper
supplied with this change. The installer verifies the exact installed
687/688 commit, DEV identity, PROD SSH identity, working source script,
local upload safety and scoped tests before creating units. It refuses to
overwrite existing unit files. On successful installation, it enables the
timer and launches the first sync asynchronously.

## Status

```bash
systemctl list-timers tracker-prod-uploads-to-dev.timer --no-pager
systemctl show tracker-prod-uploads-to-dev.service \
  -p ActiveState -p SubState -p Result -p ExecMainStatus
journalctl --no-pager -u tracker-prod-uploads-to-dev.service -n 100 -o cat
```

Expected success from a completed sync: `UPLOAD_REPLICATION=PASSED` and
`UPLOAD_REPLICATION_MISSING=0`. Service start or timer activation by
itself does **not** establish a successful transfer.

## Pausing or removing the timer

```bash
systemctl disable --now tracker-prod-uploads-to-dev.timer
```

This stops future scheduled pulls; it does not remove already synchronized
uploads. To resume: `systemctl enable --now tracker-prod-uploads-to-dev.timer`.
The PROD source is never changed by these controls.
