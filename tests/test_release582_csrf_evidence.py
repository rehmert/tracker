"""Release 582: fail-closed signed lifecycle receipt and strict-gate contracts."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker_csrf_runtime_report582.py"
RUNNER = ROOT / "scripts/tracker-browser-qualify.sh"
CONTRACT = ROOT / "tests/test_browser_qualification511.py"
BROWSER = ROOT / "tests/browser/test_csrf_dose_lifecycle582.py"


@pytest.fixture(scope="module")
def reporter():
    spec = importlib.util.spec_from_file_location("csrf582_report", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def populate(folder, reporter):
    for scheme in reporter.SCHEMES:
        row = {
            "scheme": scheme,
            "flow": "dose-lifecycle",
            "operations": [
                {"method": m, "route_pattern": path,
                 "signed_status": code, "unsigned_status": 403}
                for m, path, code in reporter.OPERATIONS
            ],
            "strict_candidate": True,
            "synthetic_qa_data_only": True,
            "signed_lifecycle_verified": True,
        }
        target = folder / f"{scheme}-dose-lifecycle.json"
        target.write_text(json.dumps(row), encoding="utf-8")
        target.chmod(0o600)


def test_582_exact_route_ledger_and_isolation_contract(reporter):
    assert reporter.OPERATIONS == (
        ("POST", "/doses", 200),
        ("POST", "/doses/{id}/edit", 303),
        ("DELETE", "/doses/{id}", 200),
    )
    script = BROWSER.read_text(encoding="utf-8")
    for marker in (
        "TRACKER_TEST_ISOLATED",
        "TRACKER_TEST_STRICT_CSRF",
        '"127.0.0.1"',
        "page.expect_response",
        "_forged(",
        'max_redirects=0',
    ):
        assert marker in script
    contract = CONTRACT.read_text(encoding="utf-8")
    assert '"tests/browser/test_csrf_dose_lifecycle582.py",' in contract
    runner = RUNNER.read_text(encoding="utf-8")
    standard, strict = runner.split("# Release 521: a second browser gate", 1)
    assert "test_csrf_dose_lifecycle582.py" not in standard
    assert strict.count("tests/browser/test_csrf_dose_lifecycle582.py") == 1
    assert strict.index("tests/browser/test_csrf_dose_lifecycle582.py") < strict.index(
        "scripts/tracker_csrf_runtime_report582.py"
    ) < strict.index("ISOLATED_STRICT_CSRF_BROWSER=PASSED")
    assert subprocess.run(["bash", "-n", str(RUNNER)], capture_output=True).returncode == 0


def test_582_receipt_rejects_tamper_missing_extra_permissions(reporter):
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="tracker-browser-qa.") as root:
        folder = Path(root) / "csrf-runtime582"
        folder.mkdir(mode=0o700)
        populate(folder, reporter)
        result = reporter.analyze(folder)
        assert result["signed_writes"] == 6
        assert result["forgery_rejections"] == 6
        target = folder / "http-dose-lifecycle.json"
        original = json.loads(target.read_text(encoding="utf-8"))
        altered = json.loads(json.dumps(original))
        altered["operations"][0]["unsigned_status"] = 200
        target.write_text(json.dumps(altered), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid or altered"):
            reporter.analyze(folder)
        target.write_text(json.dumps(original), encoding="utf-8")
        target.chmod(0o644)
        with pytest.raises(ValueError, match="private"):
            reporter.analyze(folder)
        target.chmod(0o600)
        (folder / "extra.json").write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="Missing or extra"):
            reporter.analyze(folder)
        (folder / "extra.json").unlink()
        target.unlink()
        with pytest.raises(ValueError, match="Missing or extra"):
            reporter.analyze(folder)


def test_582_rejects_symlinked_and_non_qa_path(reporter, tmp_path):
    invalid = tmp_path / "csrf-runtime582"
    invalid.mkdir()
    with pytest.raises(ValueError, match="disposable"):
        reporter.analyze(invalid)
    link = tmp_path / "linked"
    link.symlink_to(invalid, target_is_directory=True)
    with pytest.raises(ValueError, match="Symlinked"):
        reporter.analyze(link)
