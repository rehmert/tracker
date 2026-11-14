"""Release 626: dependency evidence comparison never mutates hosts."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.tracker_csrf_route_inventory620 import inventory as route_inventory
from scripts.tracker_dependency_host_compare626 import (
    compare_snapshots, diff, read_snapshot,
)
from scripts.tracker_dependency_baseline569 import BaselineError, BASELINE, read_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_626_identical_snapshots_pass_without_false_fresh_env_claim():
    baseline = read_manifest(BASELINE)["packages"]
    result = compare_snapshots(baseline, baseline, baseline)
    assert result["dev_vs_prod"] == []
    assert result["dev_vs_observed_baseline"] == []
    assert result["prod_vs_observed_baseline"] == []
    assert result["fresh_environment_reproduced"] is False
    assert result["host_comparison_only"] is True


def test_626_diff_captures_missing_added_and_changed_packages():
    assert diff({"pip": "1", "fastapi": "2"}, {"pip": "1", "new": "3"}) == [
        {"package": "fastapi", "expected": "2", "actual": None},
        {"package": "new", "expected": None, "actual": "3"},
    ]


def test_626_snapshot_rejects_unrelated_metadata_and_duplicate_names(tmp_path):
    snapshot = tmp_path / "pip.json"
    snapshot.write_text(json.dumps([{"name": "FastAPI", "version": "1"}]))
    assert read_snapshot(snapshot) == {"fastapi": "1"}
    for items in (
        [{"name": "x", "version": "1", "url": "https://secret.invalid"}],
        [{"name": "A_B", "version": "1"}, {"name": "a-b", "version": "2"}],
        [{"name": "foo", "version": "1 ; injected"}],
        [],
        {"packages": []},
    ):
        snapshot.write_text(json.dumps(items), encoding="utf-8")
        with pytest.raises((BaselineError, ValueError)):
            read_snapshot(snapshot)


def test_626_offline_cli_equal_and_drift(tmp_path):
    baseline = read_manifest(BASELINE)["packages"]
    path_dev, path_prod = tmp_path / "dev.json", tmp_path / "prod.json"
    def save(path, packages):
        path.write_text(json.dumps([
            {"name": name, "version": version}
            for name, version in packages.items()
        ]), encoding="utf-8")
    save(path_dev, baseline)
    save(path_prod, baseline)
    script = ROOT / "scripts/tracker_dependency_host_compare626.py"
    command = [sys.executable, str(script), "--dev", str(path_dev),
               "--prod", str(path_prod)]
    ok = subprocess.run(command, cwd="/tmp", text=True,
                        capture_output=True, check=True)
    assert json.loads(ok.stdout)["dev_vs_prod"] == []
    altered = dict(baseline)
    altered["fastapi"] = "999.0"
    save(path_prod, altered)
    drift = subprocess.run(command, cwd="/tmp", text=True, capture_output=True)
    assert drift.returncode == 2
    assert json.loads(drift.stdout)["prod_vs_observed_baseline"]


def test_626_existing_runtime_and_csrf_security_not_changed():
    assert 'os.environ.get("TRACKER_CSRF_ENFORCE", "0")' in (
        ROOT / "app/main.py"
    ).read_text(encoding="utf-8")
    assert len(route_inventory(ROOT)) >= 15
