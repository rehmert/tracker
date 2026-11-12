"""Release 580: strict-only lifecycle evidence and gate integrity tests."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker_csrf_runtime_report580.py"
RUNNER = ROOT / "scripts/tracker-browser-qualify.sh"
CONTRACT = ROOT / "tests/test_browser_qualification511.py"
BROWSER = ROOT / "tests/browser/test_csrf_workflows580.py"


@pytest.fixture(scope="module")
def evidence():
    spec = importlib.util.spec_from_file_location("csrf580_receipts", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_receipts(evidence, directory):
    for scheme in evidence.SCHEMES:
        for flow, operations in evidence.EXPECTED.items():
            record = {
                "scheme": scheme,
                "flow": flow,
                "operations": [
                    {"method": method, "route_pattern": path,
                     "signed_status": status, "unsigned_status": 403}
                    for method, path, status in operations
                ],
                "isolated_strict_browser": True,
                "real_user_interactions": True,
            }
            output = directory / f"{scheme}-{flow}.json"
            output.write_text(json.dumps(record) + "\n", encoding="utf-8")
            output.chmod(0o600)


def test_580_exact_source_and_runtime_contract(evidence):
    assert len(evidence.EXPECTED) == 3
    assert len(evidence.REQUIRED) == 6
    assert sum(map(len, evidence.EXPECTED.values())) == 11
    assert {"POST", "DELETE"} == {
        operation[0] for operations in evidence.EXPECTED.values()
        for operation in operations
    }
    source = BROWSER.read_text(encoding="utf-8")
    assert 'TRACKER_TEST_ISOLATED' in source
    assert 'TRACKER_TEST_STRICT_CSRF' in source
    assert '"127.0.0.1"' in source
    assert "page.expect_response" in source
    for operations in evidence.EXPECTED.values():
        for _, path, _ in operations:
            # The route templates are recorded without live IDs.
            assert path in source
    runner = RUNNER.read_text(encoding="utf-8")
    contract = CONTRACT.read_text(encoding="utf-8")
    assert '"tests/browser/test_csrf_workflows580.py",' in contract
    marker = "# Release 521: a second browser gate"
    assert runner.count(marker) == 1
    normal, strict = runner.split(marker, 1)
    assert "tests/browser/test_csrf_workflows580.py" not in normal
    assert strict.count("tests/browser/test_csrf_workflows580.py") == 1
    assert strict.index("tests/browser/test_csrf_workflows580.py") < strict.index(
        "scripts/tracker_csrf_runtime_report580.py"
    ) < strict.index("ISOLATED_STRICT_CSRF_BROWSER=PASSED")


def test_580_evidence_is_closed_schema_and_complete(evidence):
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="tracker-browser-qa.") as root:
        directory = Path(root) / "csrf-runtime580"
        directory.mkdir(mode=0o700)
        write_receipts(evidence, directory)
        result = evidence.analyze(directory)
        assert result["scenarios"] == 6
        assert result["verified_write_operations"] == 22
        assert len(result["route_patterns"]) == 11
        target = directory / "http-compound-lifecycle.json"
        record = json.loads(target.read_text(encoding="utf-8"))
        record["operations"][0]["unsigned_status"] = 200
        target.write_text(json.dumps(record), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid or unverified"):
            evidence.analyze(directory)
        record["operations"][0]["unsigned_status"] = 403
        record["csrf_cookie"] = "SHOULD_NOT_BE_SAVED"
        target.write_text(json.dumps(record), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid or unverified"):
            evidence.analyze(directory)
        record.pop("csrf_cookie")
        target.write_text(json.dumps(record), encoding="utf-8")
        target.chmod(0o644)
        with pytest.raises(ValueError, match="Insecure"):
            evidence.analyze(directory)
        target.chmod(0o600)
        target.unlink()
        with pytest.raises(ValueError, match="Missing or unexpected"):
            evidence.analyze(directory)


def test_580_rejects_untrusted_receipt_directory(evidence, tmp_path):
    wrong = tmp_path / "csrf-runtime580"
    wrong.mkdir()
    with pytest.raises(ValueError, match="disposable QA"):
        evidence.analyze(wrong)


def test_580_shell_gate_syntax():
    result = subprocess.run(
        ["bash", "-n", str(RUNNER)],
        check=False, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
