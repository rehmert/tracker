"""Read-only source-inventory regression for Release 620."""
import json
import subprocess
import sys
from pathlib import Path

from scripts.tracker_csrf_route_inventory620 import extract, inventory

ROOT = Path(__file__).resolve().parents[1]


def test_620_detects_unsafe_decorators_without_touching_runtime(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    module = app / "sample.py"
    module.write_text(
        '@router.get("/read")\n'
        'def read(): pass\n'
        '@router.post("/save")\n'
        'def save(request): pass\n'
        '@router.api_route("/multi", methods=["GET", "PATCH", "DELETE"])\n'
        'async def multi(): pass\n'
        '@router.post(dynamic_route)\n'
        'def dynamic(): pass\n',
        encoding="utf-8",
    )
    rows = extract(module, tmp_path)
    assert len(rows) == 3
    assert rows[0]["route"] == "/save"
    assert rows[0]["methods"] == ["POST"]
    assert rows[0]["has_request_parameter"]
    assert rows[1]["methods"] == ["DELETE", "PATCH"]
    assert rows[2]["route"] == "<dynamic>"
    assert all(r["review_status"] == "MANUAL_REVIEW_REQUIRED" for r in rows)


def test_620_real_inventory_is_read_only_and_has_no_security_claim():
    rows = inventory(ROOT)
    assert len(rows) >= 15
    assert any("/pages" == r["route"] and "POST" in r["methods"] for r in rows)
    assert any("/doses" == r["route"] and "POST" in r["methods"] for r in rows)
    assert all(r["review_status"] == "MANUAL_REVIEW_REQUIRED" for r in rows)
    command = subprocess.run(
        [sys.executable, str(ROOT / "scripts/tracker_csrf_route_inventory620.py")],
        capture_output=True, text=True, cwd=ROOT, check=True,
    )
    data = json.loads(command.stdout)
    assert data["runtime_csrf_verification"] is False
    assert data["total_handlers"] == len(rows)


def test_620_strict_csrf_default_and_dependency_inputs_not_modified():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert 'os.environ.get("TRACKER_CSRF_ENFORCE", "0")' in main
    from scripts.tracker_dependency_baseline569 import (
        BASELINE, CONSTRAINTS, read_manifest, read_constraints,
        validate_constraints,
    )
    validate_constraints(read_manifest(BASELINE), read_constraints(CONSTRAINTS))
