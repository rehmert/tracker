"""Release 578: fail-closed source evidence accounting and stable route attribution."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker_csrf_route_ledger578.py"


@pytest.fixture(scope="module")
def ledger():
    spec = importlib.util.spec_from_file_location("csrf_route_ledger578", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_578_all_existing_js_and_routes_preserved_without_false_clearance(ledger):
    report = ledger.build(ROOT)
    assert report["status"] == "source_only_not_strict_csrf_clearance"
    assert report["summary"]["javascript_callsites"] == 46
    assert report["summary"]["javascript_callsites"] == len(report["javascript"])
    assert report["summary"]["unsafe_routes"] == len(report["routes"])
    assert report["summary"]["native_or_htmx_sites"] == len(report["native"])
    assert report["summary"]["js_runtime_verified"] == 0
    assert report["summary"]["pending_manual_review"] == len(report["review_queue"])
    assert all(row["priority"] in ("dynamic_or_unpaired_js",
                                   "implicit_or_dynamic_native")
               for row in report["review_queue"])
    assert report["review_queue"] == sorted(
        report["review_queue"],
        key=lambda row: (row["priority"], row["file"], row["line"], row["kind"]),
    )
    assert report["summary"]["runtime_qualified_routes"] == 0
    assert report["summary"]["js_literal_source_pair_hints"] + report["summary"]["js_unresolved"] == 46
    assert all(r["runtime_qualified"] is False and
               r["strict_csrf_compatible"] is None for r in report["routes"])
    assert all(r["runtime_executed"] is False and
               r["csrf_compatible"] is None for r in report["javascript"] + report["native"])


@pytest.mark.parametrize("route,request,match", [
    ("/vials/{vial_id}", "/vials/123", True),
    ("/vials/{vial_id}", "/vials/123/edit", False),
    ("/vials/{vial_id}/preparations/{event_id}/edit",
     "/vials/12/preparations/34/edit", True),
    ("/vials/{vial_id}", "/vials/{{ id }}", False),
    ("/vials/{vial_id}", "/vials/${id}", False),
    ("/vials/{vial_id}", "/vials/123?status=all", False),
    ("/vials/{vial_id}", "/vials/123/evil", False),
])
def test_578_route_pattern_is_conservative(ledger, route, request, match):
    regex = ledger.route_pattern(route)
    assert regex is not None
    assert bool(regex.fullmatch(request)) is match


@pytest.mark.parametrize("path", [
    "url", "/vials/${vialId}", "/vials/{{vial_id}}",
    "/vials/" + "' + id", "/x?query=y", "../private", "/x/../private",
])
def test_578_dynamic_or_unsafe_paths_are_not_literal_candidates(ledger, path):
    routes = [{"method": "POST", "path": "/vials/{id}",
               "file": "app/routers/vials.py", "line": 1}]
    assert ledger.literal_route_candidates(path, routes) == []


def test_578_attribution_is_explicit_method_and_literal_path_only(ledger):
    routes = [
        {"method": "POST", "path": "/vials/{vial_id}", "file": "vials.py", "line": 1},
        {"method": "DELETE", "path": "/vials/{vial_id}", "file": "vials.py", "line": 2},
    ]
    assert [r["method"] for r in ledger.literal_route_candidates("/vials/123", routes)] == [
        "POST", "DELETE"
    ]
    assert ledger.literal_route_candidates("/vials/123/action", routes) == []


def test_578_source_provenance_is_deterministic(ledger):
    first = ledger.build(ROOT)
    second = ledger.build(ROOT)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    for js in first["javascript"]:
        for candidate in js["route_source_candidates"]:
            assert candidate in [
                {k: v for k, v in route.items()
                 if k in ("method", "path", "file", "line")}
                for route in first["routes"]
            ]
            assert js["callsite_line_method"] == candidate["method"]
            assert js["callsite_line_path"] is not None


def test_578_private_report_path_and_permissions(ledger, tmp_path):
    with pytest.raises(SystemExit) as error:
        ledger.main(["--json", str(tmp_path / "report.json")])
    assert error.value.code == 2
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="tracker-csrf578.") as name:
        output = Path(name) / "ledger.json"
        assert ledger.main(["--json", str(output)]) == 0
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["summary"]["javascript_callsites"] == 46
        assert output.stat().st_mode & 0o077 == 0
        with pytest.raises(SystemExit):
            ledger.main(["--json", str(output)])
