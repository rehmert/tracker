"""Security posture assessment without secret disclosure."""

import importlib.util
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-security-audit.py"

spec = importlib.util.spec_from_file_location(
    "tracker_security_audit",
    SCRIPT,
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def make_env(tmp_path, contents):
    path = tmp_path / "tracker.env"
    path.write_text(contents, encoding="utf-8")
    path.chmod(0o600)
    return path


def codes(items):
    return {item["code"]: item["level"] for item in items}


def test_auth_configured_and_loopback(tmp_path):
    path = make_env(
        tmp_path,
        "TRACKER_USER=operator\n"
        "TRACKER_PASS='sensitive value'\n",
    )

    found = audit.assess(
        path,
        "--host 127.0.0.1 --port 8000",
        "tracker",
    )
    result = codes(found)

    assert result["basic_auth_configured"] == "PASS"
    assert result["loopback_bind"] == "PASS"
    assert result["unprivileged_service"] == "PASS"
    assert not any(
        item["level"] == "FAIL" for item in found
    )
    assert "sensitive value" not in repr(found)


def test_partial_auth_is_a_failure(tmp_path):
    path = make_env(
        tmp_path,
        "TRACKER_USER=operator\nTRACKER_PASS=\n",
    )

    found = audit.assess(
        path,
        "--host 127.0.0.1",
        "tracker",
    )
    assert codes(found)[
        "partial_auth_configuration"
    ] == "FAIL"


def test_unprotected_all_interfaces(tmp_path):
    path = make_env(tmp_path, "")

    found = audit.assess(
        path,
        "--host 0.0.0.0 --port 8000",
        "tracker",
    )
    result = codes(found)

    assert result["basic_auth_disabled"] == "WARN"
    assert result["all_interface_bind"] == "WARN"
    assert result["exposure_without_basic_auth"] == "FAIL"


def test_all_interfaces_with_auth_is_review(tmp_path):
    path = make_env(
        tmp_path,
        "TRACKER_USER=operator\nTRACKER_PASS=secret\n",
    )
    found = audit.assess(
        path,
        "--host 0.0.0.0 --port 8000",
        "tracker",
    )
    result = codes(found)

    assert result["basic_auth_configured"] == "PASS"
    assert result["all_interface_bind"] == "WARN"
    assert "exposure_without_basic_auth" not in result


def test_permissions_and_root_service(tmp_path):
    path = make_env(
        tmp_path,
        "TRACKER_USER=operator\nTRACKER_PASS=secret\n",
    )
    path.chmod(0o644)

    found = audit.assess(
        path,
        "--host 127.0.0.1",
        "root",
    )
    result = codes(found)

    assert result["env_permissions"] == "FAIL"
    assert result["privileged_service"] == "FAIL"


def test_duplicate_auth_assignment_flagged(tmp_path):
    path = make_env(
        tmp_path,
        "TRACKER_USER=one\n"
        "TRACKER_USER=two\n"
        "TRACKER_PASS=secret\n",
    )

    found = audit.assess(
        path,
        "--host 127.0.0.1",
        "tracker",
    )
    assert codes(found)[
        "duplicate_auth_settings"
    ] == "FAIL"


def test_missing_env_fails(tmp_path):
    found = audit.assess(
        tmp_path / "missing.env",
        "--host 127.0.0.1",
        "tracker",
    )
    assert codes(found)["env_missing"] == "FAIL"


def test_no_secret_material_in_report(tmp_path):
    secret = "TopSecret-DoNotDisplay-48739"
    path = make_env(
        tmp_path,
        "TRACKER_USER=operator\n"
        f"TRACKER_PASS={secret}\n",
    )

    result = audit.assess(
        path,
        "--host 0.0.0.0",
        "tracker",
    )

    assert secret not in repr(result)
    assert "operator" not in repr(result)
