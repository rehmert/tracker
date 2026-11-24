"""Release 773: strict Google-title schema migration and backup gate contracts.

All SQLite and source checks use only synthetic fixtures.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sqlite3
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/tracker-prod-google-titles773.py"
spec = spec_from_file_location("google_title_schema773", SOURCE)
guard = module_from_spec(spec)
spec.loader.exec_module(guard)


def target():
    return subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],
                                   text=True).strip()


def test_773_exact_baseline_and_additive_source_review():
    guard.review_source(ROOT, guard.PROD_BASE, target())
    assert guard.NEW_TABLE == "google_tasks_titles773"
    assert guard.ALLOWED_APP == {
        "app/google_tasks_models769.py", "app/google_tasks_projection769.py",
        "app/routers/google_tasks769.py", "app/templates/google_tasks769.html",
    }


@pytest.mark.parametrize("bad", ["", "c"*40, "9f3e1154f30d5b2711957f51c675006f666d3440"])
def test_773_rejects_unapproved_prod_base(bad):
    with pytest.raises(ValueError, match="installed 772"):
        guard.review_source(ROOT, bad, target())


def test_773_rejects_replay_as_target():
    with pytest.raises(ValueError, match="Target cannot"):
        guard.review_source(ROOT, guard.PROD_BASE, guard.PROD_BASE)


def test_773_requires_prior_google_tables_and_absent_new_title_table(tmp_path):
    path = tmp_path/"tracker.db"
    with sqlite3.connect(path) as db:
        for name in guard.OLD_TABLES:
            db.execute(f"CREATE TABLE {name}(id INTEGER PRIMARY KEY)")
    guard.verify_schema_before(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute(f"CREATE TABLE {guard.NEW_TABLE}(id INTEGER PRIMARY KEY)")
    with pytest.raises(ValueError, match="already exists"):
        guard.verify_schema_before(tmp_path)


def test_773_rejects_missing_legacy_tables(tmp_path):
    with sqlite3.connect(tmp_path/"tracker.db") as db:
        db.execute("CREATE TABLE prior(id INTEGER PRIMARY KEY)")
    with pytest.raises(ValueError, match="Missing expected"):
        guard.verify_schema_before(tmp_path)


def test_773_resolve_relative_data_dir_and_deny_symlink(tmp_path):
    root = tmp_path/"tracker"
    data = root/"data"
    data.mkdir(parents=True)
    (data/"tracker.db").write_bytes(b"synthetic")
    env = tmp_path/"tracker.env"
    env.write_text("TRACKER_DATA_DIR=./data\n")
    assert guard.resolve_data_dir(root, env) == data
    (root/"alias").symlink_to(data, target_is_directory=True)
    env.write_text("TRACKER_DATA_DIR=alias\n")
    with pytest.raises(ValueError, match="Linked"):
        guard.resolve_data_dir(root, env)


def test_773_prod_guard_rejects_nonprod_before_live_data_access(tmp_path):
    with pytest.raises(ValueError, match="PROD-only"):
        guard.run_verified(tmp_path, guard.PROD_BASE, target())


def test_773_remote_schema_gate_before_guarded_runner():
    remote = (ROOT/"scripts/tracker_prod_remote568.sh").read_text()
    assert 'if [[ "$RELEASE" == 773 ]]' in remote
    assert "scripts/tracker-prod-google-titles773.py" in remote
    assert "RELEASE_773_PROD_SCHEMA_BACKUP=PASSED" in remote
    assert remote.index('if [[ "$RELEASE" == 773 ]]') < remote.index(
        'bash "$RUNNER"'
    )
    assert "pre-google-titles773.py" in remote
