"""Release 475 operational launch and isolation contracts."""
from pathlib import Path
import subprocess

from app.multiuser_audit474 import audit474


SCRIPT = Path(
    "scripts/tracker-multiuser-dev475.sh"
)


def test_475_shell_syntax():
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_475_explicit_dev_launch_controls():
    source = SCRIPT.read_text()

    required = (
        "TRACKER_SECONDARY_PREVIEW430",
        "TRACKER_MULTIUSER_LOGIN473",
        "TRACKER_SECONDARY_VITAL_WRITES433",
        "TRACKER_SECONDARY_DOSE_WRITES434",
        "TRACKER_SECONDARY_INVENTORY_WRITES435",
        "TRACKER_SECONDARY_FOOD_WRITES456",
        "TRACKER_SECONDARY_SUPPLY_WRITES438",
        "TRACKER_SECONDARY_SUPPLY_USE439",
        "TRACKER_SECONDARY_RECONSTITUTION_WRITES436",
        "TRACKER_SECONDARY_VIAL_CORRECTIONS437",
        "TRACKER_SECONDARY_ATTACHMENT_UPLOAD472",
    )

    for flag in required:
        assert flag in source

    assert "enable) enable" in source
    assert "disable) disable" in source
    assert "status) status" in source
    assert "check_process_flags 1" in source
    assert "check_process_flags 0" in source
    assert "rollback_enable" in source


def test_475_no_main_app_parity_claim():
    report = audit474()
    assert report["source_only"] is True
    assert report["full_main_app_cutover_ready"] is False
    assert report["runtime_security_proven"] is False


def test_475_secondary_route_coverage():
    report = audit474()

    paths = {
        (route["method"], route["path"])
        for route in report["secondary_routes"]
    }

    required = {
        ("GET", "/secondary/overview"),
        ("GET", "/secondary/food"),
        ("GET", "/secondary/vitals"),
        ("GET", "/secondary/doses"),
        ("GET", "/secondary/inventory"),
        ("GET", "/secondary/attachments"),
        ("POST", "/secondary/attachments/upload"),
    }

    assert required <= paths


def test_475_no_unauthorized_automatic_activation():
    source = SCRIPT.read_text()

    assert "require_dev()" in source
    assert "TRACKER_INSTANCE" in source
    assert "systemctl is-active" in source
    assert "systemctl daemon-reload" in source

    # No database mutation, account creation or promotion.
    for forbidden in (
        "UPDATE users",
        "DELETE FROM users",
        "DROP TABLE",
        "ALTER TABLE",
        "CREATE USER",
        "git push",
        "git reset --hard",
    ):
        assert forbidden not in source


def test_475_nonbrowser_gate_is_explicit():
    source = Path(
        "scripts/tracker-test-gate475.sh"
    ).read_text()

    assert "non-browser)" in source
    assert "--ignore=tests/browser" in source
    assert '"$PY" -m pytest' in source

    assert "multiuser)" in source
    assert "tests/test_unified_login473.py" in source
    assert "tests/test_secondary_files472.py" in source


def test_475_browser_gate_is_separate():
    source = Path(
        "scripts/tracker-test-gate475.sh"
    ).read_text()

    assert "browser)" in source
    assert "TRACKER_TEST_URL" in source
    assert "tests/browser" in source

    # Browser testing must not be silently reported as
    # successful when no target was configured.
    assert '[[ -n "${TRACKER_TEST_URL:-}" ]]' in source


def test_475_test_gate_shell_syntax():
    import subprocess

    result = subprocess.run(
        [
            "bash", "-n",
            "scripts/tracker-test-gate475.sh",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
