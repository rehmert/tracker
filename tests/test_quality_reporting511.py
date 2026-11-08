"""Release 511 audit-report guardrails: no false pass from stale results."""
from pathlib import Path
import json
import os
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_511_extended_verification_uses_fresh_reports_and_checks_failures():
    source = (ROOT / "scripts/tracker-verify-plus.sh").read_text()
    assert 'mktemp -d /tmp/tracker-verify-plus.' in source
    assert 'rm -f "$REPORT"' in source
    assert '"verification": "pending"' in source
    assert 'value.get("available") is True' in source
    assert 'value.get("failures") == 0' in source
    assert 'if result["verification"] != "passed":' in source


def test_511_security_audit_describes_partial_auth_as_fail_closed():
    source = (ROOT / "scripts/tracker-security-audit.py").read_text()
    assert '"partial_auth_configuration"' in source
    assert '"Tracker returns HTTP 503 (fail closed)."' in source
    assert "the application will not enforce Basic auth" not in source


def _run_embedded_report(tmp_path, failure_mode):
    """Execute the actual verification-report Python block on isolated fixtures."""
    fixture_dir = tmp_path / "reports"
    fixture_dir.mkdir()
    names = ("preflight.json", "quality-report.json", "release-audit.json")
    for name in names:
        path = fixture_dir / name
        if failure_mode == "missing" and name == "release-audit.json":
            continue
        if failure_mode == "corrupt" and name == "quality-report.json":
            path.write_text("{", encoding="utf-8")
            continue
        errors = ["broken audit"] if failure_mode == "errors" and name == "preflight.json" else []
        path.write_text(json.dumps({"stats": {}, "warnings": [], "errors": errors}))

    source = (ROOT / "scripts/tracker-verify-plus.sh").read_text()
    last = source.split('echo "=== Verification report ==="', 1)[1]
    code = last.split('"$PYTHON" - <<\'PY\'\n', 1)[1].split("\nPY\n", 1)[0]
    target = tmp_path / "result.json"
    code = code.replace(
        'Path("/tmp/tracker-verification-plus.json")',
        f"Path({str(target)!r})",
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        env={**os.environ, "TRACKER_VERIFY_AUDIT_DIR": str(fixture_dir)},
        capture_output=True, text=True, check=False,
    )
    return result, json.loads(target.read_text())


@pytest.mark.parametrize("failure_mode", ["none", "missing", "corrupt", "errors"])
def test_511_verification_report_never_falsely_passes(tmp_path, failure_mode):
    process, result = _run_embedded_report(tmp_path, failure_mode)
    if failure_mode == "none":
        assert process.returncode == 0, process.stderr
        assert result["verification"] == "passed"
    else:
        assert process.returncode != 0
        assert result["verification"] == "failed"
