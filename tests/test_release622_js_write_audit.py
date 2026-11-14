"""Release 622: conservative offline JavaScript request-site audit."""
import json
import subprocess
import sys
from pathlib import Path

from scripts.tracker_csrf_js_inventory622 import candidates, inventory, report

ROOT = Path(__file__).resolve().parents[1]


def test_622_extracts_literal_and_unknown_methods():
    rows = candidates(
        'fetch("/doses", {method: "POST", headers: {}});\n'
        'xhr.open("DELETE", "/doses/1");\n'
        'htmx.ajax("PATCH", "/doses/1", {});\n'
        'fetch(dynamicUrl, dynamicOptions);\n'
    )
    assert [(r["kind"], r["method_hint"]) for r in rows] == [
        ("fetch", "POST"),
        ("xhr-open", "DELETE"),
        ("htmx-ajax", "PATCH"),
        ("fetch", "UNKNOWN"),
    ]
    assert all(r["review_status"] == "MANUAL_REVIEW_REQUIRED" for r in rows)


def test_622_source_inventory_is_read_only(tmp_path):
    static = tmp_path / "app" / "static"
    static.mkdir(parents=True)
    (static / "sample.js").write_text(
        'fetch("/save", {method:"PUT"});\n',
        encoding="utf-8",
    )
    rows = inventory(tmp_path)
    assert len(rows) == 1
    assert rows[0]["file"] == "app/static/sample.js"
    assert rows[0]["method_hint"] == "PUT"
    output = report(tmp_path)
    assert output["runtime_csrf_verification"] is False
    assert output["total_candidate_call_sites"] == 1


def test_622_standalone_cli_and_production_defaults():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/tracker_csrf_js_inventory622.py")],
        cwd="/tmp", capture_output=True, text=True, check=True,
    )
    output = json.loads(result.stdout)
    assert output["runtime_csrf_verification"] is False
    assert isinstance(output["candidates"], list)
    assert all(row["review_status"] == "MANUAL_REVIEW_REQUIRED"
               for row in output["candidates"])
    assert 'os.environ.get("TRACKER_CSRF_ENFORCE", "0")' in (
        ROOT / "app/main.py"
    ).read_text(encoding="utf-8")
