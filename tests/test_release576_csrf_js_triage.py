"""Release 576: conservative, fail-closed JS source triage regressions."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker_csrf_js_triage576.py"


@pytest.fixture(scope="module")
def triage():
    spec = importlib.util.spec_from_file_location("csrf576", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_576_all_previous_callsites_retained_without_clearance(triage):
    baseline = triage.load_baseline(ROOT)
    result = triage.build(ROOT)
    assert result["status"] == "source_only_no_strict_csrf_clearance"
    assert result["summary"]["javascript_callsites"] == 46
    assert result["summary"]["pending_executable_review"] == 46
    assert result["summary"]["browser_verified"] == 0
    original = {(r["file"], r["line"], r["kind"]) for r in baseline["callsites"]}
    current = {(r["file"], r["line"], r["kind"]) for r in result["callsites"]}
    assert current == original
    assert sum(result["summary"]["triage"].values()) == 46
    assert all(r["browser_verified"] is False for r in result["callsites"])


@pytest.mark.parametrize("sample,expected,method,path", [
    ("fetch('/vitals', { method: 'POST' });", "explicit_unsafe_method_on_callsite_line", "POST", "/vitals"),
    ("fetch('/compounds');", "method_unknown", None, "/compounds"),
    ("fetch('/read', { method: 'GET' });", "explicit_get_on_callsite_line", "GET", "/read"),
    ("fetch(url, {\n  method: 'POST',\n});", "nearby_unsafe_hint_unresolved", None, None),
    ("htmx.ajax('DELETE', '/vitals/123');", "explicit_unsafe_method_on_callsite_line", "DELETE", "/vitals/123"),
])
def test_576_syntactic_evidence_is_conservative(
    triage, tmp_path, sample, expected, method, path,
):
    file = tmp_path / "app/static/qa.js"
    file.parent.mkdir(parents=True)
    file.write_text(sample + "\n", encoding="utf-8")
    record = {
        "file": "app/static/qa.js", "line": 1,
        "kind": "htmx_ajax_callsite" if sample.startswith("htmx") else "fetch_callsite",
        "classification": "test",
    }
    result = triage.inspect(record, tmp_path)
    assert (result["triage"], result["callsite_line_method"], result["callsite_line_path"]) == (expected, method, path)
    assert result["browser_verified"] is False


def test_576_nearby_method_is_not_misattributed(triage, tmp_path):
    file = tmp_path / "app/static/two.js"
    file.parent.mkdir(parents=True)
    file.write_text("fetch('/safe');\nfetch('/write', { method: 'POST' });\n", encoding="utf-8")
    result = triage.inspect({
        "file": "app/static/two.js", "line": 1,
        "kind": "fetch_callsite", "classification": "test",
    }, tmp_path)
    assert result["callsite_line_method"] is None
    assert result["callsite_line_path"] == "/safe"
    assert result["triage"] == "nearby_unsafe_hint_unresolved"


def test_576_rejects_path_escape(triage, tmp_path):
    with pytest.raises(ValueError, match="escaped repository"):
        triage.inspect({
            "file": "../../etc/passwd", "line": 1,
            "kind": "fetch_callsite", "classification": "test",
        }, tmp_path)


def test_576_private_json_and_fail_closed_path(triage, tmp_path):
    root = tmp_path / "tracker-csrf576.attack"
    root.mkdir()
    with pytest.raises(SystemExit) as err:
        triage.main(["--json", str(root / "report.json")])
    assert err.value.code == 2

    import tempfile
    with tempfile.TemporaryDirectory(prefix="tracker-csrf576.", dir="/tmp") as d:
        destination = Path(d) / "report.json"
        assert triage.main(["--json", str(destination)]) == 0
        assert json.loads(destination.read_text())["summary"]["javascript_callsites"] == 46
        assert destination.stat().st_mode & 0o077 == 0
