"""Focused static safety checks for the DEV-only minute upload timer."""
import os
from pathlib import Path

STAGE = Path(os.environ["UPLOAD_SYNC_STAGE"])
SERVICE = (STAGE / "tracker-upload-sync-dev.service").read_text()
TIMER = (STAGE / "tracker-upload-sync-dev.timer").read_text()
INSTALLER = (STAGE / "tracker-install-upload-sync-minute.sh").read_text()
SYNC = Path("/opt/tracker/scripts/tracker-prod-uploads-to-dev645.sh").read_text()


def test_minute_calendar_and_single_service_target():
    assert "OnCalendar=*-*-* *:*:00" in TIMER
    assert "AccuracySec=1s" in TIMER
    assert "RandomizedDelaySec=0" in TIMER
    assert "Persistent=false" in TIMER
    assert "Unit=tracker-upload-sync-dev.service" in TIMER
    assert "WantedBy=timers.target" in TIMER


def test_service_only_runs_existing_additive_script_on_dev():
    assert "Type=oneshot" in SERVICE
    assert "Environment=PROD_SSH=root@tracker-prod" in SERVICE
    assert "ExecStart=/usr/bin/bash /opt/tracker/scripts/tracker-prod-uploads-to-dev645.sh" in SERVICE
    assert "TimeoutStartSec=900" in SERVICE
    assert "User=root" in SERVICE
    assert "ExecStart=ssh" not in SERVICE
    assert "ExecStart=rsync" not in SERVICE


def test_existing_sync_is_additive_read_only_on_prod():
    assert "rsync -rt --ignore-existing" in SYNC
    assert '--no-owner --no-group' in SYNC
    assert ' "$SOURCE:$REMOTE_DATA/uploads/" "/opt/tracker/data/uploads/"' in SYNC
    commands = "\n".join(line for line in SYNC.splitlines() if not line.lstrip().startswith("#"))
    assert "--delete" not in commands
    assert "DELETE=NONE" in SYNC
    assert 'SOURCE="$PROD_SSH"' in SYNC
    assert "remote instance is not explicitly PROD" in SYNC
    assert "Database replication or deployment currently active" in SYNC


def test_installer_refuses_unintended_host_and_overwrite():
    assert '"$(hostname -s)" == tracker-dev' in INSTALLER
    assert '"$(git rev-parse HEAD)" == "$BASE"' in INSTALLER
    assert 'tracker-instance-check653.py --config /etc/tracker.env' in INSTALLER
    assert 'cmp -s "$STAGE/$unit" "$destination"' in INSTALLER
    assert "Refuse to overwrite existing, nonmatching unit" in INSTALLER
    assert 'systemctl enable --now "$TIMER"' in INSTALLER
    assert 'systemctl start --no-block "$SERVICE"' in INSTALLER
    assert "--instance PROD" not in INSTALLER
