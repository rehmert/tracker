"""Release 574: distinguish Jinja parameter shapes from real browser proof.

No template execution, arbitrary evaluation, installed service requests,
or live database reads. All route registration uses pytest isolation.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker_csrf_inventory572.py"


@pytest.fixture(scope="module")
def audit574():
    spec = importlib.util.spec_from_file_location("csrf_shape574", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _item(method, target, kind="html_form"):
    record = {
        "kind": kind,
        "file": "app/templates/dummy.html",
        "line": 1,
        "method": method,
    }
    record["action" if kind == "html_form" else "target"] = target
    return record


def _triage(audit, method, target, routes, kind="html_form"):
    return audit.classify_browser_entrypoints(
        {"html_and_htmx": [_item(method, target, kind)]},
        [
            {"method": verb, "path": path, "mounted": False}
            for verb, path in routes
        ],
    )[0]["classification"]


@pytest.mark.parametrize("target,registered", [
    ("/compounds/{{ c.id }}/delete", "/compounds/{cid}/delete"),
    ("/purchases/{{ p.id }}/vials/{{ v.id }}/delete",
     "/purchases/{pid}/vials/{vid}/delete"),
    ("/labs/{{ rep.id }}/import-csv",
     "/labs/{rid}/import-csv"),
    ("/food/quick/{{ e.product_id }}",
     "/food/quick/{product_id}"),
    ("/vendor-prices/shipping/{{ rule.id }}/delete",
     "/vendor-prices/shipping/{rule_id}/delete"),
])
def test_574_jinja_id_segments_shape_match_without_rendering(
    audit574, target, registered,
):
    assert _triage(
        audit574, "POST", target, [("POST", registered)]
    ) == "templated_route_shape_matched"


@pytest.mark.parametrize("target", [
    "/purchases/{{ p.id }}/delete/missing",
    "/purchases/{{ p.name }}/delete",
    "/purchases/{{ '/purchases/' ~ p.id }}/delete",
    "/purchases/{% if p %}5{% endif %}/delete",
    "/purchases/{{ p.id|safe }}/delete",
    "/purchases/{{ p.id }}/{{ arbitrary }}",
    "//attacker.example/purchases/{{ p.id }}/delete",
    "/purchases/{{ p.id }}/delete?next={{ arbitrary }}",
])
def test_574_reject_uncertain_or_non_id_template_shapes(audit574, target):
    result = _triage(
        audit574, "POST", target,
        [("POST", "/purchases/{pid}/delete")],
    )
    assert result != "templated_route_shape_matched", (target, result)


def test_574_method_mismatch_does_not_inflate_shape_matches(audit574):
    assert _triage(
        audit574, "POST", "/vitals/{{ r.id }}",
        [("DELETE", "/vitals/{rid}")],
    ) == "manual_dynamic_or_implicit"


def test_574_mounted_route_shapes_stay_manual(audit574):
    records = audit574.classify_browser_entrypoints(
        {"html_and_htmx": [
            _item("POST", "/secondary/vitals/{{ r.id }}/edit")
        ]},
        [{"method": "POST",
          "path": "/secondary/vitals/{rid}/edit",
          "mounted": True}],
    )
    assert records[0]["classification"] == "manual_dynamic_or_implicit"


def test_574_real_inventory_preserves_compatibility_review_requirements(
    audit574,
):
    from app.main import app
    report = audit574.build(app)
    s = report["summary"]
    assert s["registered_unsafe_routes"] == 144
    assert s["root_routes_missing_global_dependencies"] == 0
    assert s["templated_route_shapes_matched"] >= 1
    assert s["literal_browser_write_routes_unmatched"] == 0
    assert s["browser_writes_needing_manual_resolution"] == (
        s["browser_targets_unresolved_without_shape_match"]
        + s["templated_route_shapes_matched"]
    )
    assert any(
        item["classification"] == "templated_route_shape_matched"
        and "{{" in item["target"]
        for item in report["browser_entrypoint_triage"]
    )
    assert any(
        "does not verify rendered URLs" in limitation
        for limitation in report["limitations"]
    )
