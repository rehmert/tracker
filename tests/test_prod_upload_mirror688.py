"""DEV-only one-way upload mirror: source- and unit-level safety contracts."""
from pathlib import Path
import configparser
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/tracker-prod-uploads-to-dev645.sh"
SERVICE = ROOT / "deploy/tracker-prod-uploads-to-dev.service"
TIMER = ROOT / "deploy/tracker-prod-uploads-to-dev.timer"
INSTALLER = ROOT / "scripts/tracker-install-prod-upload-mirror688.sh"


def test_mirror_remains_additive_and_dev_only():
    body = SOURCE.read_text()
    assert "UPLOAD_REPLICATION=PASSED" in body
    assert "--ignore-existing" in body
    assert "--no-owner --no-group" in body
    assert "no --delete" in body  # source explicitly prohibits deletion
    assert "rsync -rt" in body
    assert 'exec 9>/run/lock/tracker-db-sync.lock' in body
    assert 'labels[0].upper() != "DEV"' in body
    assert 'labels[0].upper() != "PROD"' in body
    assert "UPLOAD_REPLICATION_HASH_MISMATCH" in body
    assert "PROD_DATABASE=UNMODIFIED" in body
    assert "DEV_DATABASE=UNMODIFIED" in body


def test_unit_runs_only_on_dev_with_a_sandbox_and_existing_source():
    body = SERVICE.read_text()
    assert "ConditionHost=tracker-dev" in body
    assert "Environment=PROD_SSH=root@tracker-prod" in body
    assert "ExecStart=/usr/bin/bash /opt/tracker/scripts/tracker-prod-uploads-to-dev645.sh" in body
    assert "ExecStartPre=/opt/tracker/.venv/bin/python /opt/tracker/scripts/tracker-instance-check653.py" in body
    for field in ("ProtectSystem=strict", "NoNewPrivileges=yes",
                  "PrivateTmp=yes", "ProtectHome=read-only",
                  "ReadWritePaths=/opt/tracker/data/uploads /run/lock",
                  "MemoryMax=512M", "TasksMax=96", "TimeoutStartSec=15min"):
        assert field in body
    assert "tracker.db" not in body
    assert "ExecStart=/usr/bin/bash /opt/tracker/scripts/tracker-prod-uploads-to-dev645.sh" in body


def test_timer_is_regular_no_overlap_or_missed_runs_storm():
    c = configparser.ConfigParser(interpolation=None)
    c.read_string(TIMER.read_text())
    assert c.get("Unit", "ConditionHost") == "tracker-dev"
    assert c.get("Timer", "OnCalendar") == "*-*-* *:*:00"
    assert c.get("Timer", "Unit") == "tracker-prod-uploads-to-dev.service"
    assert c.get("Timer", "Persistent") == "false"
    assert c.get("Install", "WantedBy") == "timers.target"


def test_installer_has_fail_closed_checks_and_no_prod_writes():
    body = INSTALLER.read_text()
    for token in (
        "tracker-dev", "tracker-instance-check653.py",
        "tracker-db-sync.lock", "systemd-analyze verify",
        'systemctl enable --now "$TIMER"',
        'systemctl start --no-block "$SERVICE"',
        "ssh -n -T", "root@tracker-prod",
    ):
        assert token in body
    assert "rsync " not in body
    assert "systemctl restart tracker" not in body
    assert "systemctl restart tracker-backup" not in body
    assert 'systemctl enable --now "$TIMER"' in body
    assert "PROD_DATABASE=UNMODIFIED" not in body  # no false install success claim
    result = subprocess.run(["bash", "-n", str(INSTALLER)], capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
