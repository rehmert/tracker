"""Release 573: triage native HTML and HTMX write paths without false safety claims.

The real runtime inventory is imported under pytest's isolated database.
Synthetic cases exercise exact, templated, unsafe and unresolved actions.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/tracker_csrf_inventory572.py"


@pytest.fixture(scope="module")
def audit573():
    spec = importlib.util.spec_from_file_location("csrf_inventory573", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _entry(kind, method, target, line=10):
    item = {
        "kind": kind, "method": method, "file": "app/templates/test.html",
        "line": line,
    }
    item["action" if kind == "html_form" else "target"] = target
    return item


def test_573_literal_native_and_htmx_actions_match_effective_routes(audit573):
    routes = [
        {"method": "POST", "path": "/compounds", "mounted": False},
        {"method": "DELETE", "path": "/vitals/{rid}", "mounted": False},
        {"method": "POST", "path": "/coas/{cid}/verify", "mounted": False},
    ]
    static = {"html_and_htmx": [
        _entry("html_form", "post", "/compounds"),
        _entry("htmx", "DELETE", "/vitals/123"),
        _entry("html_form", "post", "/coas/17/verify?follow=true"),
    ]}
    results = audit573.classify_browser_entrypoints(static, routes)
    assert [r["classification"] for r in results] == [
        "literal_route_matched",
        "literal_route_matched",
        "literal_route_matched",
    ]


@pytest.mark.parametrize("action,category", [
    ("/missing", "literal_route_not_matched"),
    ("/compounds/{{ id }}/edit", "manual_dynamic_or_implicit"),
    ("", "manual_dynamic_or_implicit"),
    ("https://other.example/write", "manual_absolute_or_external"),
    ("//evil.example/write", "manual_absolute_or_external"),
    ("submit", "manual_relative_or_fragment"),
    ("#save", "manual_relative_or_fragment"),
])
def test_573_unresolved_forms_never_misclassified_as_covered(
    audit573, action, category,
):
    static = {"html_and_htmx": [
        _entry("html_form", "post", action),
    ]}
    routes = [{"method": "POST", "path": "/compounds", "mounted": False}]
    results = audit573.classify_browser_entrypoints(static, routes)
    assert results[0]["classification"] == category


def test_573_mounted_routes_are_not_guessed_to_be_root_routes(audit573):
    static = {"html_and_htmx": [_entry("htmx", "DELETE", "/secret/1")]}
    routes = [
        {"method": "DELETE", "path": "/secret/{rid}", "mounted": True}
    ]
    results = audit573.classify_browser_entrypoints(static, routes)
    assert results[0]["classification"] == "literal_route_not_matched"


def test_573_real_inventory_includes_browser_review_categories(audit573):
    from app.main import app
    report = audit573.build(app)
    summary = report["summary"]
    assert summary["registered_unsafe_routes"] > 100
    assert summary["root_routes_missing_global_dependencies"] == 0
    assert summary["literal_browser_write_routes_matched"] >= 1
    assert summary["html_htmx_write_sites"] == len(
        report["browser_entrypoint_triage"]
    )
    assert report["javascript_request_callsites"]
    assert any(
        row["target"] == "/compounds"
        and row["classification"] == "literal_route_matched"
        for row in report["browser_entrypoint_triage"]
    )
    assert all(row["classification"] in {
        "literal_route_matched", "literal_route_not_matched",
        "manual_dynamic_or_implicit",
        "manual_absolute_or_external", "manual_relative_or_fragment",
    } for row in report["browser_entrypoint_triage"])
