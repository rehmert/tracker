"""Release 771: offline exact-source PROD Google Tasks migration guard tests.

No installed host, user SQLite, external service or Google account is accessed.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sqlite3
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/tracker-prod-google-schema771.py"
spec = spec_from_file_location("release771_google_prod_guard", SOURCE)
guard = module_from_spec(spec)
spec.loader.exec_module(guard)


def target_sha():
    return subprocess.check_output(["git", "-C", str(ROOT),
                                    "rev-parse", "HEAD"], text=True).strip()


def test_771_exact_768_to_qualified_771_source_review():
    guard.review_source(ROOT, guard.PROD_BASE, target_sha())


@pytest.mark.parametrize("base", ["", "f" * 40, "9f3e1154f30d5b2711957f51c675006f666d3440"])
def test_771_other_prod_bases_are_rejected(base):
    with pytest.raises(ValueError, match="PROD 768"):
        guard.review_source(ROOT, base, target_sha())


def test_771_rejects_old_or_replayed_target():
    for target in (guard.PROD_BASE, guard.DEV_770):
        with pytest.raises(ValueError):
            guard.review_source(ROOT, guard.PROD_BASE, target)


def test_771_models_are_exact_four_immutable_tables():
    model = (ROOT / guard.SOURCE).read_text(encoding="utf-8")
    assert sorted(guard.EXPECTED_TABLES.values()) == sorted([
        "google_tasks_connection769", "google_tasks_lists769",
        "google_tasks_links769", "google_tasks_exclusions769",
    ])
    assert model.count('__tablename__') == 4
    assert "app/models.py" not in guard.ALLOWED_APPLICATION_PATHS
    assert "app/db.py" not in guard.ALLOWED_APPLICATION_PATHS


def test_771_relative_live_data_dir_and_symlink_rejection(tmp_path):
    root = tmp_path / "tracker"
    root.mkdir()
    data = root / "data"
    data.mkdir()
    (data / "tracker.db").write_bytes(b"synthetic")
    cfg = tmp_path / "tracker.env"
    cfg.write_text("TRACKER_DATA_DIR='./data'\n")
    assert guard.live_data_dir(root, cfg) == data
    linked = root / "alias"
    linked.symlink_to(data, target_is_directory=True)
    cfg.write_text("TRACKER_DATA_DIR=alias\n")
    with pytest.raises(ValueError):
        guard.live_data_dir(root, cfg)
    cfg.write_text("TRACKER_DATA_DIR=missing\n")
    with pytest.raises(ValueError):
        guard.live_data_dir(root, cfg)


def test_771_sqlite_integrity_and_no_existing_google_tables(tmp_path):
    with sqlite3.connect(tmp_path / "tracker.db") as db:
        db.execute("CREATE TABLE existing_intakes(id INTEGER PRIMARY KEY)")
    guard.verify_database(tmp_path)
    with sqlite3.connect(tmp_path / "tracker.db") as db:
        db.execute("CREATE TABLE google_tasks_links769(key TEXT PRIMARY KEY)")
    with pytest.raises(ValueError, match="preexisting"):
        guard.verify_database(tmp_path)


def test_771_guard_refuses_any_nonprod_execution(monkeypatch):
    monkeypatch.setattr(guard.os, "geteuid", lambda: 1000)
    with pytest.raises(ValueError, match="PROD root-only"):
        guard.run_verified(Path("/opt/tracker"), guard.PROD_BASE, target_sha())


def test_771_remote_guard_is_before_production_runner():
    remote = (ROOT / "scripts/tracker_prod_remote568.sh").read_text()
    assert 'if [[ "$RELEASE" == 771 ]]' in remote
    assert '--base "$BASE" --target "$TARGET"' in remote
    assert "RELEASE_771_PROD_SCOPED=PASSED" in remote
    assert remote.index('if [[ "$RELEASE" == 771 ]]') < remote.index(
        'bash "$RUNNER"'
    )
