# Release 1 — Data Protection

Tracker remains entirely self-contained. No external health-metric integrations.

## Contents

- Consistent SQLite online backup (safe with an active WAL-mode application).
- All files under `data/uploads/` included, including COAs and lab uploads.
- SHA-256 checksums for every archived file, archive manifest, and SQLite integrity check.
- Server-side manual creation and history at `/backups`.
- CLI creation, verification, listing, and UTC daily/weekly/monthly retention.
- Optional systemd daily timer; no schema changes.

## Deploy

1. Back up your existing `data/` and `.env` independently before replacing code.
2. Deploy the updated project to `/opt/tracker`, retaining existing `data/` and `.env`.
3. Ensure `/opt/tracker/.venv` is installed and `tracker.service` works as before.
4. Set backup storage path with `TRACKER_BACKUP_DIR` (default `/opt/tracker/backups`). **Prefer a separate disk or mounted backup volume.** Ensure the service account can write it.
5. Restart `sudo systemctl restart tracker.service`; visit `/backups` to create a backup.
6. For scheduled backups, install the units:

```bash
sudo cp deploy/tracker-backup.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tracker-backup.timer
sudo systemctl start tracker-backup.service
sudo systemctl status tracker-backup.service
sudo systemctl list-timers tracker-backup.timer
```

**Important:** `deploy/tracker-backup.service` assumes Linux account `tracker`, application path `/opt/tracker`, and venv `/opt/tracker/.venv`. Change those settings to match your actual `tracker.service`. If `TRACKER_DATA_DIR` or `TRACKER_BACKUP_DIR` is set for the application, set the same environment variables for the backup service (e.g., with `EnvironmentFile=`). Default retention: 7 daily, 4 weekly, 3 monthly snapshots, with overlap deduplicated. Retention runs after a verified new backup.

Manual CLI:

```bash
cd /opt/tracker
.venv/bin/python -m scripts.tracker_backup create
.venv/bin/python -m scripts.tracker_backup list
.venv/bin/python -m scripts.tracker_backup verify /opt/tracker/backups/tracker-YYYYMMDDTHHMMSSffffffZ.zip
```

## Restore (offline, deliberately not exposed in web UI)

1. Stop Tracker: `sudo systemctl stop tracker.service`.
2. **Preserve** the current `data/` as a separate rollback copy.
3. Verify the selected backup using the CLI `verify` command.
4. Restore **only into a fresh, empty staging directory**, then replace the data directory after review:

```bash
mkdir -p /tmp/tracker-restore
unzip -q /path/to/verified-tracker-backup.zip -d /tmp/tracker-restore
# Remove manifest, which is backup metadata, not app data:
rm /tmp/tracker-restore/manifest.json
# Review contents before replacing your existing data directory.
# Copy tracker.db and uploads/ from staging to the configured TRACKER_DATA_DIR.
# Remove old tracker.db-wal and tracker.db-shm ONLY while the service is stopped,
# after preserving the rollback copy, before restarting.
sudo systemctl start tracker.service
```

**Never extract an unverified or untrusted archive into a live data directory.** Confirm the service's file permissions after restoring. Reconcile any changes made after the selected backup; restoration rolls back both the DB and uploads to the archive's snapshot.

## Operational considerations

- A ZIP backup is a point-in-time SQLite snapshot, but uploads may change during archive creation. For a strict cross-file point-in-time snapshot, pause writes or stop the application while backing up.
- Backups stored on the same disk do not protect against disk failure. Replicate archives to separately managed storage and periodically test a restore.
- Backups may contain sensitive health data. Restrict permissions and encrypt backup storage; the ZIP format here is **not encrypted**.
- A manual backup request can take time for large upload collections. For large datasets, prefer the scheduled CLI service.
