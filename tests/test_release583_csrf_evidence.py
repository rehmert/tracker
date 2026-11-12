"""Release 583: preparation CSRF evidence, fixture accounting and isolation gate."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/tracker-browser-qualify.sh"
CONTRACT = ROOT / "tests/test_browser_qualification511.py"
BROWSER = ROOT / "tests/browser/test_csrf_preparations583.py"
FIXTURE = ROOT / "scripts/tracker_csrf_fixture583.py"
REPORT = ROOT / "scripts/tracker_csrf_runtime_report583.py"


@pytest.fixture(scope="module")
def reporter():
    spec = importlib.util.spec_from_file_location("csrf583", REPORT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def populate(folder, reporter):
    for scheme in reporter.SCHEMES:
        data = {
            "scheme": scheme, "flow": "preparation-lifecycle",
            "operations": [
                {"method": m, "route_pattern": p,
                 "signed_status": code, "unsigned_status": 403}
                for m, p, code in reporter.OPERATIONS
            ],
            "strict_candidate": True, "synthetic_qa_data_only": True,
            "signed_lifecycle_verified": True,
            "inventory_verified_separately": True,
        }
        target = folder / f"{scheme}-preparation-lifecycle.json"
        target.write_text(json.dumps(data), encoding="utf-8")
        target.chmod(0o600)


def test_583_exact_scope_and_isolated_gate(reporter):
    assert reporter.OPERATIONS == (
        ("POST", "/vials/{id}/reconstitute", 303),
        ("POST", "/vials/{id}/filter", 303),
        ("POST", "/vials/{id}/preparations/{event}/edit", 303),
        ("POST", "/vials/{id}/preparations/{event}/delete", 303),
    )
    browser = BROWSER.read_text(encoding="utf-8")
    for needle in (
        "TRACKER_TEST_ISOLATED", "TRACKER_TEST_STRICT_CSRF",
        "127.0.0.1", "page.expect_response", "_rejected(",
        "csrf_token", "max_redirects=0",
    ):
        assert needle in browser
    # Shared base layout has multiple POST forms. A browser test must
    # resolve the unique correction form through its Save control.
    assert 'correction = page.locator("form[method=' not in browser
    assert 'get_by_role("button", name="Save correction", exact=True)' in browser
    assert 'xpath=ancestor::form[1]' in browser
    fixture = FIXTURE.read_text(encoding="utf-8")
    for needle in (
        "TRACKER_TEST_ISOLATED", "TRACKER_TEST_STRICT_CSRF",
        "TRACKER_INSTANCE", r"tracker-browser-qa\.", "remaining_qty",
        "PreparationSupply", "SupplyUsage",
    ):
        assert needle in fixture
    assert '"tests/browser/test_csrf_preparations583.py",' in CONTRACT.read_text(
        encoding="utf-8"
    )
    runner = RUNNER.read_text(encoding="utf-8")
    standard, strict = runner.split("# Release 521: a second browser gate", 1)
    assert "test_csrf_preparations583.py" not in standard
    assert strict.count("tests/browser/test_csrf_preparations583.py") == 1
    assert strict.index("tracker_csrf_fixture583.py\" seed") < strict.index(
        "tests/browser/test_csrf_preparations583.py"
    ) < strict.index("tracker_csrf_runtime_report583.py") < strict.index(
        "tracker_csrf_fixture583.py\" verify"
    ) < strict.index("ISOLATED_STRICT_CSRF_BROWSER=PASSED")
    result = subprocess.run(["bash", "-n", str(RUNNER)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_583_rejects_tampered_missing_extra_and_public_receipts(reporter):
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="tracker-browser-qa.") as root:
        directory = Path(root) / "csrf-runtime583"
        directory.mkdir(mode=0o700)
        populate(directory, reporter)
        assert reporter.analyze(directory)["signed_writes"] == 8
        assert reporter.analyze(directory)["forgery_rejections"] == 8
        path = directory / "http-preparation-lifecycle.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        bad = json.loads(json.dumps(original))
        bad["operations"][2]["unsigned_status"] = 200
        path.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid evidence"):
            reporter.analyze(directory)
        path.write_text(json.dumps(original), encoding="utf-8")
        path.chmod(0o644)
        with pytest.raises(ValueError, match="Non-private"):
            reporter.analyze(directory)
        path.chmod(0o600)
        (directory / "extra.json").write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="Missing or extra"):
            reporter.analyze(directory)
        (directory / "extra.json").unlink()
        path.unlink()
        with pytest.raises(ValueError, match="Missing or extra"):
            reporter.analyze(directory)


def test_583_refuses_non_qa_and_symlinked_receipt_roots(reporter, tmp_path):
    wrong = tmp_path / "csrf-runtime583"
    wrong.mkdir()
    with pytest.raises(ValueError, match="disposable"):
        reporter.analyze(wrong)
    link = tmp_path / "alias"
    link.symlink_to(wrong, target_is_directory=True)
    with pytest.raises(ValueError, match="Symlinked"):
        reporter.analyze(link)
