"""Release 396: Labs and COA attachment authorization."""

import ast
import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException, Request
from fastapi.params import Depends as DependsParameter
from fastapi.routing import APIRoute

from app import attachment_scope396 as guard
from app.db import get_db
from app.scoped_db390 import get_scoped_db390
from app.routers import labs, coas


ROOT = Path(__file__).resolve().parents[1]


def request():
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/labs",
        "raw_path": b"/labs",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 50000),
        "server": ("tracker.test", 443),
    })


def test_both_routers_have_guard():
    for module in (labs, coas):
        routes = [
            route for route in module.router.routes
            if isinstance(route, APIRoute)
        ]

        assert routes

        for route in routes:
            dependencies = [
                item.dependency
                for item in route.dependencies
            ]

            assert guard.require_attachment_scope396 in dependencies, (
                module.__name__,
                route.path,
            )


@pytest.mark.parametrize(
    "module_name,expected",
    [("labs", 19), ("coas", 12)],
)
def test_database_dependencies_scoped(module_name, expected):
    path = ROOT / "app/routers" / f"{module_name}.py"
    tree = ast.parse(path.read_text())

    scoped = 0
    legacy = 0

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if not isinstance(node.func, ast.Name):
            continue

        if node.func.id != "Depends" or not node.args:
            continue

        value = node.args[0]

        if not isinstance(value, ast.Name):
            continue

        scoped += value.id == "get_scoped_db390"
        legacy += value.id == "get_db"

    assert scoped == expected
    assert legacy == 0
    if module_name == "labs":
        # The Release 500 historical CSV export is a new scoped endpoint;
        # keep it behind the same attachment and workspace dependencies.
        export = next(
            route for route in labs.router.routes
            if isinstance(route, APIRoute)
            and route.path == "/labs/trends/{analyte_key}/export.csv"
        )
        dependencies = [item.dependency for item in export.dependencies]
        assert guard.require_attachment_scope396 in dependencies
        from app.attachment_files400 import require_attachment_workspace400
        assert require_attachment_workspace400 in dependencies


def test_scoped_dependency_preserves_override():
    parameter = inspect.signature(
        get_scoped_db390
    ).parameters["db"]

    dependency = parameter.default

    assert isinstance(dependency, DependsParameter)
    assert dependency.dependency is get_db


def test_missing_session_fails_closed(monkeypatch):
    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: True,
    )

    def reject(_):
        raise HTTPException(403, "Not authenticated")

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        reject,
    )

    with pytest.raises(HTTPException) as error:
        guard.require_attachment_scope396(request())

    assert error.value.status_code == 403


def test_legacy_mode_preserves_existing_fixture_behavior(
    monkeypatch,
):
    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: False,
    )

    def resolver_must_not_run(_):
        raise AssertionError("Unexpected session resolver")

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        resolver_must_not_run,
    )

    assert guard.require_attachment_scope396(
        request()
    ) is None


def test_session_mode_checks_both_directories(
    monkeypatch,
    tmp_path,
):
    from app.user_storage388 import StoragePaths

    root = tmp_path
    coa = root / "uploads" / "coa"
    labs_dir = root / "uploads" / "labs"

    coa.mkdir(parents=True)
    labs_dir.mkdir(parents=True)

    storage = StoragePaths(
        user_id=1,
        mode="legacy-admin",
        root=root,
        database=root / "tracker.db",
        coa=coa,
        labs=labs_dir,
        backups=root / "backups",
    )

    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        lambda _: storage,
    )

    monkeypatch.setattr(
        guard.config,
        "UPLOAD_DIR",
        coa,
    )

    monkeypatch.setattr(
        guard.config,
        "LAB_DIR",
        labs_dir,
    )

    assert guard.require_attachment_scope396(
        request()
    ) is None

    monkeypatch.setattr(
        guard.config,
        "LAB_DIR",
        root / "another-user" / "labs",
    )

    with pytest.raises(HTTPException) as error:
        guard.require_attachment_scope396(request())

    assert error.value.status_code == 503


def test_untrusted_future_account_fails_closed(monkeypatch):
    from app.user_storage388 import StoragePaths

    root = Path("/tmp/tracker-inactive-account")

    storage = StoragePaths(
        user_id=2,
        mode="reserved-inactive",
        root=root,
        database=root / "tracker.db",
        coa=root / "uploads" / "coa",
        labs=root / "uploads" / "labs",
        backups=root / "backups",
    )

    monkeypatch.setattr(
        guard.session_auth385,
        "enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        guard,
        "resolve_authenticated_storage",
        lambda _: storage,
    )

    with pytest.raises(HTTPException) as error:
        guard.require_attachment_scope396(request())

    assert error.value.status_code == 403


def test_attachment_paths_use_verified_workspace_boundary():
    """Existing attachment locations are preserved by the resolver.

    Routers must no longer reference process-wide paths directly.
    """
    labs_source = (
        ROOT / "app/routers/labs.py"
    ).read_text()

    coa_source = (
        ROOT / "app/routers/coas.py"
    ).read_text()

    assert "config.LAB_DIR" not in labs_source
    assert "config.UPLOAD_DIR" not in coa_source

    assert (
        'attachment_directory400("labs")'
        in labs_source
    )
    assert (
        'attachment_directory400("coa")'
        in coa_source
    )

    assert (
        'attachment_file400("labs", rep.stored_name)'
        in labs_source
    )
    assert (
        'attachment_file400("coa", c.stored_name)'
        in coa_source
    )

    # Preserve commit/rollback cleanup of uploaded files.
    for source in (labs_source, coa_source):
        assert "uploaded_transaction" in source
        assert "delete_after_commit" in source

    # Legacy paths are now owned by the central resolver.
    helper = (
        ROOT / "app/attachment_files400.py"
    ).read_text()

    assert "config.LAB_DIR" in helper
    assert "config.UPLOAD_DIR" in helper


def test_additional_accounts_still_disabled():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3, 4):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)
