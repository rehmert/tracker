"""Release 579: source-independent strict-browser evidence receipt checks."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess

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


def test_579_manifest_is_exact_and_covers_source_workflows(report):
    assert set(report.FLOWS) == {
        "mobile-weight", "mobile-bp", "mobile-water",
        "notes-preview", "notes-visual-fetch", "native-compound",
    }
    assert len(report.FLOWS) * len(report.SCHEMES) == 12
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


def test_579_two_tracked_javascript_callsites_not_overclaimed(report):
    source = report.reviewed_js_source_callsites(ROOT)
    assert source["tracked_js_callsites"] == 50
    assert source["witnessed_js_callsites"] == 2
    assert source["not_witnessed_in_579"] == 48
    assert source["unqualified_coa_multi651_callsites"] == 1
    assert len(source["source_refs"]) == 2
    assert any("tracker-mobile-quick528.js:" in ref
               for ref in source["source_refs"])
    assert any("notes_editor.js:" in ref
               for ref in source["source_refs"])


def test_651_coa_post_source_contract_matches_exactly_and_fails_closed(report):
    source = (ROOT / report.COA_MULTI651_SOURCE).read_text(encoding="utf-8")
    lines = source.splitlines()
    callsites = [index for index, line in enumerate(lines)
                 if "fetch(form.action, {" in line]
    assert len(callsites) == 1
    callsite = callsites[0]
    report.verify_coa_multi651_request_lines(lines, callsite)
    # This assertion specifically guards against treating an expected string
    # as a full list element. The real JavaScript is indented.
    assert lines[callsite + 1].startswith("        method:")

    for before, after in (
        ('method: "POST"', 'method: "GET"'),
        ("body: new FormData(form)", "body: null"),
        ('headers: {Accept: "application/json"}', "headers: {}"),
        ('credentials: "same-origin"', 'credentials: "omit"'),
        ("fetch(form.action, {", "fetch('https://elsewhere.test', {"),
    ):
        modified = list(lines)
        offset = next(i for i in range(callsite, callsite + 6)
                      if before in modified[i])
        modified[offset] = modified[offset].replace(before, after)
        with pytest.raises(ValueError, match="re-review required"):
            report.verify_coa_multi651_request_lines(modified, callsite)

    with pytest.raises(ValueError, match="re-review required"):
        report.verify_coa_multi651_request_lines(lines, -1)
    with pytest.raises(ValueError, match="re-review required"):
        report.verify_coa_multi651_request_lines(lines[:callsite + 2], callsite)


def test_579_report_requires_exact_isolated_witnesses(report):
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
        assert result["observed_write_scenarios"] == 12
        assert result["distinct_tested_paths"] == [
            "/compounds", "/food/water", "/pages/preview", "/vitals",
        ]
        assert result["javascript_flows"] == 8
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
        first.write_text(json.dumps({
            "scheme": "http", "flow": "mobile-weight", "method": "POST",
            "path": "/vitals", "accepted_status": 200,
            "denied_status": 403, "signed_browser_request": True,
            "runtime_observed": True, "isolated_candidate": True,
        }), encoding="utf-8")
        first.chmod(0o644)
        with pytest.raises(ValueError, match="Unsafe browser witness"):
            report.analyze(directory)
        first.chmod(0o600)
        (directory / "unexpected.json").write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="Missing or unexpected"):
            report.analyze(directory)


def test_579_runner_shell_syntax_is_valid():
    outcome = subprocess.run(["bash", "-n", str(RUNNER)],
                             capture_output=True, text=True, check=False)
    assert outcome.returncode == 0, outcome.stderr
