"""Release 621: offline template-write/unsafe-route review candidates."""
import json
import subprocess
import sys
from pathlib import Path

from scripts.tracker_csrf_form_crosswalk621 import (
    WriteControls, clean_path, controls, crosswalk, route_pattern,
)

ROOT = Path(__file__).resolve().parents[1]


def test_621_static_native_and_htmx_controls(tmp_path):
    templates = tmp_path / "app" / "templates"
    templates.mkdir(parents=True)
    (templates / "example.html").write_text(
        '<form method="POST" action="/pages"><input></form>\n'
        '<form method="get" action="/pages"></form>\n'
        '<button hx-delete="/doses/123"></button>\n'
        '<form hx-post="/doses"><button>Save</button></form>\n'
        '<form method="post" action="{{ url }}"></form>\n',
        encoding="utf-8",
    )
    rows = controls(tmp_path)
    assert [(r["method"], r["path"], r["kind"]) for r in rows] == [
        ("POST", "/pages", "native-form"),
        ("DELETE", "/doses/123", "htmx"),
        ("POST", "/doses", "htmx"),
        ("POST", "{{ url }}", "native-form"),
    ]
    assert clean_path("/doses/123?x=1") == "/doses/123"
    assert clean_path("{{ url }}") is None
    assert clean_path("relative/action") is None
    assert route_pattern("/doses/{dose_id}").fullmatch("/doses/123")
    assert not route_pattern("/doses/{dose_id}").fullmatch("/pages/123")


def test_621_real_crosswalk_marks_every_row_for_review():
    report = crosswalk(ROOT)
    assert report["runtime_csrf_verification"] is False
    assert report["total_declared_unsafe_handlers"] >= 15
    assert report["total_visible_template_write_controls"] >= 10
    assert all(x["review_status"] == "MANUAL_REVIEW_REQUIRED"
               for x in report["controls"])
    assert any(x["method"] == "POST" for x in report["controls"])
    assert report["unmatched_or_dynamic_controls"] >= 0


def test_621_absolute_path_cli_emits_json_without_writes():
    script = ROOT / "scripts" / "tracker_csrf_form_crosswalk621.py"
    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True,
        cwd="/tmp", check=True,
    )
    data = json.loads(result.stdout)
    assert data["schema_version"] == 1
    assert data["runtime_csrf_verification"] is False
    assert isinstance(data["controls"], list)
