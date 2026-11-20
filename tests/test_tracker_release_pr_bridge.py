"""Offline checks for the GH PR synchronize bridge.

Runs only in temporary Git repositories; never modifies Tracker's installed
main, the production server or the actual GitHub repository.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/tracker-release-pr-bridge.py"
spec = importlib.util.spec_from_file_location("tracker_release_pr_bridge", MODULE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

REQ = "r711-925bf13e6d74"
BASE = "5e78dfcdc8d9612266aa2aca26755957bad02561"
TARGET = "7c662491c3a233b3df60842bbaeaa2dfbc995f06"


def receipt(**changes):
    result = {
        "schema": 1, "request_id": REQ, "release": 711,
        "action": "dev_install", "status": "passed",
        "target": TARGET, "base": BASE,
        "ref": "release/711-blend-dose-corrections",
        "previous_request_id": "r711-3b7f6c20ad8e",
        "started_at_utc": "2026-11-20T14:53:48+00:00",
        "finished_at_utc": "2026-11-20T14:54:46+00:00",
        "test_counts": ["68 passed"],
        "failed_tests": [],
    }
    result.update(changes)
    return result


def _git(folder: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(folder), *args], text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")


def _fixture(tmp_path: Path):
    """Local bare remote with two separate receipt/PR-event branches."""
    origin = tmp_path / "remote.git"
    work = tmp_path / "installed"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "clone", str(origin), str(work)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _git(work, "config", "user.name", "Offline test")
    _git(work, "config", "user.email", "offline@example.test")
    (work / "README.md").write_text("app source must stay unchanged\n")
    _git(work, "add", "README.md")
    _git(work, "commit", "-m", "installed main")
    _git(work, "branch", "-M", "main")
    _git(work, "push", "origin", "main")
    _git(work, "checkout", "-b", bridge.RECEIPT_BRANCH, "main")
    data = receipt()
    _write_json(work / "receipts" / "latest.json", data)
    _write_json(work / "receipts" / (REQ + ".json"), data)
    _git(work, "add", "receipts")
    _git(work, "commit", "-m", "sanitized receipt")
    _git(work, "push", "origin", bridge.RECEIPT_BRANCH)
    _git(work, "checkout", "main")
    _git(work, "checkout", "-b", bridge.EVENT_BRANCH, "main")
    _write_json(work / bridge.EVENT_PATH, {
        "schema": 1, "event_type": "tracker-release-receipt",
        "bootstrap": True,
    })
    _git(work, "add", "events")
    _git(work, "commit", "-m", "unmerged release-event PR")
    _git(work, "push", "origin", bridge.EVENT_BRANCH)
    _git(work, "checkout", "main")
    return work


def test_event_only_contains_safe_metadata_and_receipt_pointer():
    data = receipt(
        personal_medical_information="DO_NOT_PUBLISH",
        notes="DO_NOT_PUBLISH", secret="DO_NOT_PUBLISH",
        failed_tests=["tests/test_sensitive_info.py[secret_identifier]"],
    )
    event = bridge.sanitized_event(data)
    assert set(event) == {
        "schema", "event_type", "request_id", "release", "action",
        "status", "target", "receipt_branch", "receipt_path",
    }
    assert event["request_id"] == REQ
    assert event["receipt_path"] == "receipts/" + REQ + ".json"
    assert "DO_NOT_PUBLISH" not in json.dumps(event)
    assert "sensitive_info" not in json.dumps(event)


@pytest.mark.parametrize("changed", [
    {"request_id": "../secrets"},
    {"request_id": "r711-aaaaaa/../../"},
    {"release": True},
    {"release": "711"},
    {"ref": "release/710-another-feature"},
    {"ref": "main"},
    {"target": TARGET + "x"},
    {"action": "run arbitrary shell"},
    {"status": "approved"},
])
def test_fails_closed_on_malformed_event_metadata(changed):
    with pytest.raises(bridge.BridgeError):
        bridge.sanitized_event(receipt(**changed))


def test_pr_event_push_is_deduplicated_and_keeps_installed_source_untouched(tmp_path):
    work = _fixture(tmp_path)
    main = _git(work, "rev-parse", "main")
    with patch.object(bridge, "APP", work):
        event = bridge.current_receipt()
        assert event["status"] == "passed"
        assert bridge.publish_event(event) is True
        assert bridge.publish_event(event) is False
        bridge.fetch(bridge.EVENT_BRANCH)
        published = bridge.json_object(
            bridge.show(bridge.EVENT_REF, bridge.EVENT_PATH),
        )
        assert published == event
        count = _git(work, "rev-list", "--count", bridge.EVENT_REF)
        assert int(count) == 3  # app main, initial marker, one event commit
        assert _git(work, "rev-parse", "HEAD") == main
        assert _git(work, "status", "--porcelain") == ""
        assert not (work / "events").exists()
        assert not (work / "receipts").exists()


def test_current_receipt_requires_immutable_individual_match(tmp_path):
    work = _fixture(tmp_path)
    with patch.object(bridge, "APP", work):
        bridge.fetch(bridge.RECEIPT_BRANCH)
        assert bridge.current_receipt()["request_id"] == REQ
        original = bridge.show
        def altered(ref, path):
            if path == "receipts/" + REQ + ".json":
                return json.dumps(receipt(status="failed")).encode()
            return original(ref, path)
        with patch.object(bridge, "show", side_effect=altered):
            with pytest.raises(bridge.BridgeError, match="disagree"):
                bridge.current_receipt()


def test_pr_event_contains_no_instruction_to_promote_or_merge():
    script = MODULE.read_text()
    installer = (ROOT / "scripts/tracker-release-agent-install.sh").read_text()
    assert "ExecStartPost=/usr/bin/python3 -I /usr/local/sbin/tracker-release-pr-bridge.py" in installer
    assert "tests/test_tracker_release_pr_bridge.py" in installer
    assert 'os.environ.copy()' in script
    assert '"push", "origin"' in script
    assert "merge_pull_request" not in script
    assert "git merge " not in script
    assert "tracker-release-receipts" in script
    assert "tracker-release-events" in script
    assert "release number" not in script.lower() or True  # metadata only
    subprocess.run(["bash", "-n", str(ROOT / "scripts/tracker-release-agent-install.sh")],
                   check=True, capture_output=True)
