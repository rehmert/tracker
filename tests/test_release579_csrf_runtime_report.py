"""Release 579: source-independent strict-browser evidence receipt checks."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker_csrf_runtime_report579.py"
BROWSER = ROOT / "tests/browser/test_csrf_runtime579.py"
RUNNER = ROOT / "scripts/tracker-browser-qualify.sh"


@pytest.fixture(scope="module")
def report():
    spec = importlib.util.spec_from_file_location("csrf579_report", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def witnesses(report, tmp_path, monkeypatch):
    # The gate only accepts a disposable browser QA path below /tmp.
    # Tests use pytest's isolated tmp_path then monkeypatch just the
    # path validation boundary, never a real application or PROD URL.
    directory = tmp_path / "csrf-runtime579"
    directory.mkdir()
    for scheme in report.SCHEMES:
        for flow, (path, status) in report.FLOWS.items():
            record = {
                "scheme": scheme, "flow": flow, "method": "POST",
                "path": path, "accepted_status": status,
                "denied_status": 403,
                "signed_browser_request": True,
                "runtime_observed": True, "isolated_candidate": True,
            }
            file = directory / f"{scheme}-{flow}.json"
            file.write_text(json.dumps(record), encoding="utf-8")
            file.chmod(0o600)
    # Only mock Path.resolve, not stat/permissions or analysis logic.
    original = report.Path.resolve
    def fake_resolve(path, *args, **kwargs):
        if str(path) == str(directory):
            return report.Path("/tmp/tracker-browser-qa.ABCDEFGH/csrf-runtime579")
        return original(path, *args, **kwargs)
    # Prefer testing the actual path instead of replacing filesystem
    # resolution, which would make fixture file lookup impossible.
    monkeypatch.setattr(report.re, "fullmatch", re.fullmatch)
    return directory


def test_579_report_rejects_non_qa_paths(report, witnesses):
    with pytest.raises(ValueError, match="disposable browser"):
        report.analyze(witnesses)


def test_579_manifest_is_exact_and_covers_source_workflows(report):
    assert set(report.FLOWS) == {
        "mobile-weight", "mobile-bp", "mobile-water",
        "notes-preview", "native-compound",
    }
    assert len(report.FLOWS) * len(report.SCHEMES) == 10
    text = BROWSER.read_text(encoding="utf-8")
    assert "_record_evidence" in text
    assert 'TRACKER_TEST_STRICT_CSRF' in text
    assert '"127.0.0.1"' in text
    for path, _ in report.FLOWS.values():
        assert path in text
    runner = RUNNER.read_text(encoding="utf-8")
    assert "tests/browser/test_csrf_runtime579.py" in runner
    assert "scripts/tracker_csrf_runtime_report579.py" in runner
    assert runner.index("tests/browser/test_csrf_runtime579.py") < runner.index(
        "scripts/tracker_csrf_runtime_report579.py"
    ) < runner.index("ISOLATED_STRICT_CSRF_BROWSER=PASSED")


def test_579_report_requires_exact_isolated_witnesses(report, tmp_path):
    # Use genuine /tmp tree under a private fixture namespace if pytest's
    # tmp path happens to be elsewhere; this calls no app and no network.
    import tempfile
    with tempfile.TemporaryDirectory(prefix="tracker-browser-qa.", dir="/tmp") as base:
        root = Path(base)
        directory = root / "csrf-runtime579"
        directory.mkdir(mode=0o700)
        for scheme in report.SCHEMES:
            for flow, (path, status) in report.FLOWS.items():
                value = {
                    "scheme": scheme, "flow": flow, "method": "POST",
                    "path": path, "accepted_status": status,
                    "denied_status": 403,
                    "signed_browser_request": True, "runtime_observed": True,
                    "isolated_candidate": True,
                }
                file = directory / f"{scheme}-{flow}.json"
                file.write_text(json.dumps(value) + "\n", encoding="utf-8")
                file.chmod(0o600)
        result = report.analyze(directory)
        assert result["observed_write_scenarios"] == 10
        assert result["distinct_tested_paths"] == [
            "/compounds", "/food/water", "/pages/preview", "/vitals",
        ]
        assert result["javascript_flows"] == 6
        assert result["htmx_flows"] == 2
        assert result["native_flows"] == 2
        first = directory / "http-mobile-weight.json"
        value = json.loads(first.read_text(encoding="utf-8"))
        value["denied_status"] = 200
        first.write_text(json.dumps(value), encoding="utf-8")
        with pytest.raises(ValueError, match="Unverified"):
            report.analyze(directory)
        value["denied_status"] = 403
        value["token"] = "SHOULD_NEVER_BE_STORED"
        first.write_text(json.dumps(value), encoding="utf-8")
        with pytest.raises(ValueError, match="schema"):
            report.analyze(directory)
        first.unlink()
        with pytest.raises(ValueError, match="Missing or unexpected"):
            report.analyze(directory)


def test_579_runner_shell_syntax_is_valid():
    outcome = subprocess.run(["bash", "-n", str(RUNNER)],
                             capture_output=True, text=True, check=False)
    assert outcome.returncode == 0, outcome.stderr
