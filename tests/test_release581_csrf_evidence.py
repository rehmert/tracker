"""Release 581: strict-only inventory/dose browser gate and receipt regressions."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker_csrf_runtime_report581.py"
BROWSER = ROOT / "tests/browser/test_csrf_inventory581.py"
RUNNER = ROOT / "scripts/tracker-browser-qualify.sh"
CONTRACT = ROOT / "tests/test_browser_qualification511.py"


@pytest.fixture(scope="module")
def report():
    spec = importlib.util.spec_from_file_location("csrf581_evidence", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def populate(report, folder):
    for scheme in report.SCHEMES:
        for name in (*report.POSITIVE, *report.NEGATIVE):
            if name in report.POSITIVE:
                method, route, status = report.POSITIVE[name]
                kind = "positive"
            else:
                method, route = report.NEGATIVE[name]
                status = None
                kind = "negative"
            row = {
                "scheme": scheme, "flow": name, "kind": kind,
                "method": method, "route_pattern": route,
                "signed_status": status, "unsigned_status": 403,
                "strict_candidate": True, "synthetic_qa_data_only": True,
            }
            target = folder / f"{scheme}-{name}.json"
            target.write_text(json.dumps(row), encoding="utf-8")
            target.chmod(0o600)


def test_581_closed_contract_and_strict_only_module(report):
    assert len(report.POSITIVE) == 2
    assert len(report.NEGATIVE) == 6
    assert len(report.REQUIRED) == 16
    browser = BROWSER.read_text(encoding="utf-8")
    assert 'TRACKER_TEST_ISOLATED' in browser
    assert 'TRACKER_TEST_STRICT_CSRF' in browser
    assert 'page.expect_response' in browser
    assert '"127.0.0.1"' in browser
    for method, path, *_ in report.POSITIVE.values():
        assert method in browser and path in browser
    runner = RUNNER.read_text(encoding="utf-8")
    contract = CONTRACT.read_text(encoding="utf-8")
    assert '"tests/browser/test_csrf_inventory581.py",' in contract
    marker = "# Release 521: a second browser gate"
    standard, strict = runner.split(marker, 1)
    assert "tests/browser/test_csrf_inventory581.py" not in standard
    assert strict.count("tests/browser/test_csrf_inventory581.py") == 1
    assert strict.index("tests/browser/test_csrf_inventory581.py") < strict.index(
        "scripts/tracker_csrf_runtime_report581.py"
    ) < strict.index("ISOLATED_STRICT_CSRF_BROWSER=PASSED")


def test_581_report_rejects_tampering_missing_extra_and_insecure_files(report):
    with tempfile.TemporaryDirectory(
        dir="/tmp", prefix="tracker-browser-qa."
    ) as root:
        folder = Path(root) / "csrf-runtime581"
        folder.mkdir(mode=0o700)
        populate(report, folder)
        info = report.analyze(folder)
        assert info["browser_cases"] == 16
        assert info["signed_positive_cases"] == 4
        assert info["negative_only_cases"] == 12
        assert len(info["signed_write_route_patterns"]) == 2
        assert len(info["negative_only_route_patterns"]) == 6

        target = folder / "http-dose-create.json"
        original = json.loads(target.read_text(encoding="utf-8"))
        data = {**original, "signed_status": 200}
        target.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="Unverified or altered"):
            report.analyze(folder)
        data = {**original, "extra_secret": "must never persist"}
        target.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="Unverified or altered"):
            report.analyze(folder)
        target.write_text(json.dumps(original), encoding="utf-8")
        target.chmod(0o644)
        with pytest.raises(ValueError, match="Non-private"):
            report.analyze(folder)
        target.chmod(0o600)
        target.unlink()
        with pytest.raises(ValueError, match="Missing or extra"):
            report.analyze(folder)


def test_581_rejects_wrong_and_symlinked_export_roots(report, tmp_path):
    wrong = tmp_path / "csrf-runtime581"
    wrong.mkdir()
    with pytest.raises(ValueError, match="disposable"):
        report.analyze(wrong)
    link = tmp_path / "linked"
    link.symlink_to(wrong, target_is_directory=True)
    with pytest.raises(ValueError, match="Symlinked"):
        report.analyze(link)


def test_581_browser_runner_shell_syntax():
    result = subprocess.run(
        ["bash", "-n", str(RUNNER)], capture_output=True, text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
