"""Release 511 audit-report guardrails: no false pass from stale results."""
from pathlib import Path

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
