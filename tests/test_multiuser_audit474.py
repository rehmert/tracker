"""Release 474: cutover blockers must remain visible."""
import ast
import json
import subprocess
import sys
from pathlib import Path

from app.multiuser_audit474 import audit474


def test_474_audit_discovers_real_routes():
    report = audit474()

    assert report["schema"] == (
        "tracker-multiuser-cutover-audit474"
    )
    assert report["source_only"] is True
    assert report["primary_route_count"] > 0
    assert report["secondary_route_count"] > 0

    paths = {
        (item["method"], item["path"])
        for item in report["secondary_routes"]
    }

    for route in (
        ("GET", "/secondary/overview"),
        ("GET", "/secondary/vitals"),
        ("GET", "/secondary/doses"),
        ("GET", "/secondary/food"),
        ("GET", "/secondary/inventory"),
        ("GET", "/secondary/attachments"),
        ("POST", "/secondary/attachments/upload"),
    ):
        assert route in paths, route


def test_474_reports_main_cutover_blockers():
    report = audit474()

    assert report["full_main_app_cutover_ready"] is False
    assert report["runtime_security_proven"] is False

    assert all(report["checks"].values())

    blockers = {
        row["id"]
        for row in report["blocking_items"]
    }

    assert {
        "ADMIN_ONLY_SCOPE",
        "ADMIN_ONLY_ENGINE",
        "FOOD_GLOBAL_ENGINE",
        "ROUTE_PARITY_NOT_PROVEN",
    } <= blockers


def test_474_no_false_activation_claims():
    report = audit474()
    serialized = json.dumps(report)

    assert '"full_main_app_cutover_ready": false' in serialized
    assert '"runtime_security_proven": false' in serialized
    assert report["source_only"] is True


def test_474_cli_json_and_fail_closed_gate():
    completed = subprocess.run(
        [sys.executable, "-m", "app.multiuser_audit474"],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr

    result = json.loads(completed.stdout)
    assert result["primary_route_count"] > 0
    assert result["blocking_items"]

    blocked = subprocess.run(
        [
            sys.executable,
            "-m", "app.multiuser_audit474",
            "--require-full-cutover",
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert blocked.returncode == 2
    assert json.loads(
        blocked.stdout
    )["full_main_app_cutover_ready"] is False


def test_474_no_security_module_changes():
    from app.multiuser_audit474 import ROOT474

    source = (
        ROOT474 / "app" / "multiuser_audit474.py"
    ).read_text()
    tree = ast.parse(source)

    for forbidden in (
        "sqlite3.connect(",
        "create_engine(",
        "session.commit(",
        "db.commit(",
        "os.environ[",
        "subprocess.run(",
        "FileResponse(",
    ):
        assert forbidden not in source

    assert tree is not None
