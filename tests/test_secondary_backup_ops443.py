"""Release 443: scheduled secondary backup safeguards, health and retention."""

import os
import sqlite3
import stat
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from app import config, session_auth385 as auth
from app.secondary_backup_ops443 import (
    LOCK_NAME, _exclusive_runner443, archives443, backup_directory443,
    health443, prune443, run_backup443,
)
from app.secondary_backup442 import verify_secondary_backup442
from app.user_accounts427 import stage_secondary_account427
from app.user_bootstrap426 import initialize_staged_workspace426


@pytest.fixture
def ready(tmp_path, monkeypatch):
    root = tmp_path / "data"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(config, "DATA_DIR", root)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")

    auth.bootstrap("operator", "administrator-secure-password-443")
    (root / auth.FLAG).write_text("enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, root)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-secure-password-{uid}-443",
        )
        with sqlite3.connect(root / "users" / str(uid) / "tracker.db") as db:
            db.execute("""
                INSERT INTO compounds(name,category,notes,primary_unit)
                VALUES (?, 'other', '', 'mg')
            """, (f"PRIVATE-443-{uid}",))
    with sqlite3.connect(root / "tracker.db") as db:
        db.execute("CREATE TABLE admin_only (secret TEXT)")
        db.execute("INSERT INTO admin_only VALUES ('unchanged')")
    return root, tmp_path / "root-private-recovery"


def _run(ready, *, keep=14):
    _, dest = ready
    return run_backup443(dest, keep=keep)


def test_scheduled_runner_restores_and_reports_fresh_archive(ready):
    root, dest = ready
    original_admin = (root / "tracker.db").read_bytes()

    result = _run(ready)
    assert result["verified_user_count"] == 2
    assert result["retained"] == 1
    assert result["pruned"] == []
    assert result["globally_atomic"] is False

    archive = archives443(dest)[0]
    assert str(archive) == result["archive"]
    assert verify_secondary_backup442(archive)["restore_verified"] is True
    assert stat.S_IMODE(dest.stat().st_mode) == 0o700
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    assert (dest / LOCK_NAME).is_file()
    assert stat.S_IMODE((dest / LOCK_NAME).stat().st_mode) == 0o600

    report = health443(dest)
    assert report["healthy"] is True
    assert report["archive_count"] == 1
    assert report["user_count"] == 2
    assert report["reason"] == "ok"
    assert (root / "tracker.db").read_bytes() == original_admin


def test_health_missing_stale_and_future_archives_do_not_pass(ready):
    _, dest = ready
    backup_directory443(dest, create=True)
    missing = health443(dest)
    assert missing["healthy"] is False
    assert missing["reason"] == "no_verified_archive"
    assert missing["archive_count"] == 0

    _run(ready)
    now = datetime.now(timezone.utc)
    assert health443(dest, now=now + timedelta(hours=48))["healthy"] is False
    assert health443(dest, now=now - timedelta(hours=1))["healthy"] is False


def test_retention_prunes_verified_older_archives_only(ready):
    _, dest = ready
    for i in range(4):
        result = _run(ready, keep=2)
        assert result["verified_user_count"] == 2

    files = archives443(dest)
    assert len(files) == 2
    assert len({p.name for p in files}) == 2
    assert all(verify_secondary_backup442(path)["user_count"] == 2 for path in files)

    unrelated = dest / "operator-note.txt"
    unrelated.write_text("operator note must never be deleted")
    assert prune443(dest, keep=2) == []
    assert unrelated.read_text() == "operator note must never be deleted"


def test_corrupted_old_archive_aborts_retention_without_deletion(ready):
    _, dest = ready
    for _ in range(3):
        _run(ready, keep=14)
    paths = archives443(dest)
    assert len(paths) == 3

    oldest = paths[-1]
    with zipfile.ZipFile(oldest, "a") as archive:
        archive.writestr("tampered.txt", b"invalid archive")
    names_before = {p.name for p in archives443(dest)}

    with pytest.raises(ValueError):
        prune443(dest, keep=2)
    assert {p.name for p in archives443(dest)} == names_before

    with pytest.raises(ValueError):
        _run(ready, keep=2)
    # New archive may have been successfully published, but none was pruned.
    assert names_before <= {p.name for p in archives443(dest)}
    assert oldest.exists()


def test_corrupted_newest_archive_never_reports_healthy(ready):
    _, dest = ready
    _run(ready)
    latest = archives443(dest)[0]
    with zipfile.ZipFile(latest, "a") as z:
        z.writestr("other.bin", b"not in manifest")
    with pytest.raises(ValueError):
        health443(dest)
    assert latest.exists()


def test_exclusive_lock_guards_both_run_and_manual_prune(ready):
    _, dest = ready
    backup_directory443(dest, create=True)
    with _exclusive_runner443(dest):
        with pytest.raises(RuntimeError, match="already running"):
            run_backup443(dest)
        with pytest.raises(RuntimeError, match="already running"):
            prune443(dest)
    assert archives443(dest) == []
    assert _run(ready)["retained"] == 1


def test_symlinks_and_wrong_permissions_fail_closed(ready):
    _, dest = ready
    backup_directory443(dest, create=True)
    os.chmod(dest, 0o750)
    with pytest.raises(ValueError, match="0700"):
        health443(dest)
    os.chmod(dest, 0o700)

    _run(ready)
    latest = archives443(dest)[0]
    os.chmod(latest, 0o644)
    with pytest.raises(ValueError, match="permissions"):
        health443(dest)
    os.chmod(latest, 0o600)

    link = dest / "tracker-secondary-20261106T010000000000Z-aaaaaaaa.zip"
    link.symlink_to(latest)
    with pytest.raises(ValueError, match="Symlinked"):
        archives443(dest)
    link.unlink()


def test_invalid_retention_and_non_dev_are_rejected(ready, monkeypatch):
    _, dest = ready
    backup_directory443(dest, create=True)

    # Invalid parameters must remain rejected.
    for bad in (0, 1, 366, True, 1.5, "7"):
        with pytest.raises(ValueError):
            run_backup443(dest, keep=bad)
        with pytest.raises(ValueError):
            prune443(dest, keep=bad)

    for bad in (0, 721, "24", True):
        with pytest.raises(ValueError):
            health443(dest, max_age_hours=bad)

    # Release 523 enables secondary backup operations in PROD.
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")

    result = run_backup443(dest)
    assert result["verified_user_count"] == 2
    assert result["retained"] == 1

    report = health443(dest)
    assert report["healthy"] is True
    assert report["user_count"] == 2

    assert prune443(dest, keep=2) == []
    assert len(archives443(dest)) == 1

    # Unknown environments must still fail closed.
    monkeypatch.setattr(config, "instance_label", lambda: "UNKNOWN")

    with pytest.raises(PermissionError):
        run_backup443(dest)
    with pytest.raises(PermissionError):
        health443(dest)
    with pytest.raises(PermissionError):
        prune443(dest)



def test_timer_is_opt_in_and_prod_untouched():
    from pathlib import Path
    timer = Path("scripts/tracker-secondary-backup443.timer").read_text()
    service = Path("scripts/tracker-secondary-backup443.service").read_text()
    runner = Path("scripts/tracker-secondary-scheduled443.sh").read_text()
    cli = Path("scripts/tracker-secondary-ops443.py").read_text()
    release = Path("scripts/tracker-release.sh").read_text()

    assert "OnCalendar=*-*-* 03:15:00" in timer
    assert "Persistent=true" in timer
    assert "WantedBy=timers.target" in timer
    assert "NoNewPrivileges=yes" in service
    assert "UMask=0077" in service
    assert "TRACKER_INSTANCE" in runner
    assert '"$TRACKER_INSTANCE" == DEV' in runner
    assert "--keep 14" in runner
    assert 'choices=("run", "status", "prune")' in cli
    assert "systemctl enable" not in release
    assert "systemctl enable" not in runner
    assert "systemctl start" not in runner


def test_readiness_clarifies_scheduling_not_active_by_default():
    from pathlib import Path
    source = Path("app/secondary_preview430.py").read_text()
    assert "optional nightly" in source
    assert "never enabled by deployment" in source
    assert "off-host encryption" in source
    assert "live restore function" in source
    assert "tracker-secondary-ops443.py status" in source
