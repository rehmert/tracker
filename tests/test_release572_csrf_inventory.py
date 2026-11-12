"""Release 572: structural and negative-path coverage for CSRF inventory.

All app imports occur under existing pytest isolation. This module does not
change configuration, start web servers, or access live user data.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from starlette.routing import Route
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker_csrf_inventory572.py"


@pytest.fixture(scope="module")
def audit():
    spec = importlib.util.spec_from_file_location("csrf_inventory572", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def report(audit):
    from app.main import app
    return audit.build(app)


def test_known_write_routes_registered(report):
    from app.main import app
    keys = {(entry["method"], entry["path"]) for entry in report["routes"]}
    sample = [
        (type(route).__name__, getattr(route, "path", ""),
         sorted(getattr(route, "methods", ()) or ()))
        for route in app.routes[:8]
    ]
    assert ("POST", "/compounds") in keys, (
        f"Inventory registered {len(report['routes'])} unsafe routes; "
        f"FastAPI app has {len(app.routes)} routes: {sample}"
    )
    assert ("POST", "/coas/new") in keys
    assert ("POST", "/labs/import-csv") in keys
    assert ("POST", "/pk/compounds") in keys
    assert any(method == "DELETE" and path.startswith("/vitals/")
               for method, path in keys)


def test_application_routes_keep_auth_and_multipart_dependencies(report):
    # Dependency presence is structural evidence, not auth effectiveness.
    assert report["summary"]["registered_unsafe_routes"] > 100
    assert report["summary"]["root_routes_missing_global_dependencies"] == 0
    assert not report["global_dependency_gaps"]
    for route in report["routes"]:
        if not route["mounted"]:
            assert route["global_auth_dependency"]
            assert route["global_multipart_dependency"]


def test_multipart_upload_routes_covered_by_static_inventory(report):
    upload_paths = {path for _method, path in report["file_upload_writes"]}
    assert "/labs/import-csv" in upload_paths
    assert "/coas/new" in upload_paths


def test_runtime_and_static_scan_differences_are_visible(report):
    summary = report["summary"]
    assert summary["static_declared_routes"] > 100
    assert summary["registered_unsafe_routes"] >= 100
    assert "runtime_missing_from_static_scanner" in summary
    assert "static_missing_from_runtime_registration" in summary
    assert report["status"] == "inventory_only_manual_review_required"
    assert len(report["routes"]) == summary["registered_unsafe_routes"]


def test_coverage_never_claims_all_routes_are_secure(report):
    assert report["limitations"]
    assert all(row["needs_manual_endpoint_review"] for row in report["routes"])
    assert any("not a complete coverage matrix" in x for x in report["limitations"])
    assert "/labs/import-csv" in report["strict_browser_example_paths"]


def test_unprotected_test_app_is_flagged_for_review(audit):
    # A synthetic route lacking both of Tracker's global dependencies
    # must NOT be accidentally classified as guarded.
    fake = FastAPI()

    @fake.post("/unsafe")
    def unsafe():
        return {"ok": True}

    rows = audit.registered_writes(fake)
    assert len(rows) == 1
    assert rows[0]["global_auth_dependency"] is False
    assert rows[0]["global_multipart_dependency"] is False


def test_mounted_subapp_is_explicit_and_not_assumed_global(audit):
    parent = FastAPI()
    child = FastAPI()

    @child.post("/write")
    def post():
        return {"ok": True}

    parent.mount("/private", child)
    rows = audit.registered_writes(parent)
    assert len(rows) == 1
    assert rows[0]["path"] == "/private/write"
    assert rows[0]["mounted"] is True


def test_lazy_included_router_effective_context_is_scanned(audit):
    # Reproduce FastAPI 0.162's _IncludedRouter/effective_candidates API,
    # independent of the runner's FastAPI version. Never infer that a
    # lazy wrapper without .methods has no write endpoints.
    child = FastAPI()

    @child.post("/write")
    def write():
        return {"ok": True}

    original = next(
        route for route in child.routes
        if getattr(route, "path", "") == "/write"
    )
    effective = SimpleNamespace(
        original_route=original,
        methods={"POST"},
        path="/from-lazy-router/write",
        dependant=original.dependant,
    )

    class _IncludedRouter:
        def effective_candidates(self):
            return [effective]

    parent = FastAPI()
    parent.router.routes.append(_IncludedRouter())
    rows = audit.registered_writes(parent)
    assert len(rows) == 1
    assert rows[0]["method"] == "POST"
    assert rows[0]["path"] == "/from-lazy-router/write"
    assert rows[0]["global_auth_dependency"] is False


def test_lazy_included_router_refuses_unusable_expansion(audit):
    class _IncludedRouter:
        pass

    parent = FastAPI()
    parent.router.routes.append(_IncludedRouter())
    with pytest.raises(ValueError, match="expansion unavailable"):
        audit.registered_writes(parent)


def test_unsafe_starlette_route_is_not_silently_ignored(audit):
    fake = FastAPI()

    async def handler(request):
        return {"ok": True}

    fake.router.routes.append(Route("/plain", handler, methods=["POST"]))
    with pytest.raises(ValueError, match="cannot be classified"):
        audit.registered_writes(fake)


def test_empty_unsafe_inventory_is_not_silent_success(audit):
    fake = FastAPI()
    with pytest.raises(ValueError, match="No registered unsafe routes"):
        audit.registered_writes(fake)


def test_source_avoid_service_and_live_secret_access():
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in (
        '"systemctl"', '"restart"', '"git", "push"',
        '"/etc/tracker.env"', "subprocess.run(",
        '"TRACKER_CSRF_ENFORCE", "1"',
    ):
        assert forbidden not in source


def test_environment_gate_rejects_missing_data_dir(audit, monkeypatch):
    monkeypatch.delenv("TRACKER_DATA_DIR", raising=False)
    with pytest.raises(SystemExit) as exc:
        audit.main([])
    assert exc.value.code == 2


def test_environment_gate_rejects_relative_data_dir(audit, monkeypatch):
    monkeypatch.setenv("TRACKER_DATA_DIR", "data")
    with pytest.raises(SystemExit) as exc:
        audit.main([])
    assert exc.value.code == 2


def test_environment_gate_refuses_live_data_directory(audit, monkeypatch):
    monkeypatch.setenv("TRACKER_DATA_DIR", "/opt/tracker/data")
    with pytest.raises(SystemExit) as exc:
        audit.main([])
    assert exc.value.code == 2


def test_environment_gate_refuses_unrelated_tmp_directory(audit, monkeypatch,
                                                           tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("TRACKER_DATA_DIR", str(data))
    with pytest.raises(SystemExit) as exc:
        audit.main([])
    assert exc.value.code == 2
