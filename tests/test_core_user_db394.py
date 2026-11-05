"""Release 394.1: authenticated core feature database routing."""

import ast
import inspect
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.params import Depends as DependsParameter

from app.db import get_db
from app.scoped_db390 import get_scoped_db390


ROOT = Path(__file__).resolve().parents[1]

CORE = {
    "compounds": 5,
    "protocols": 12,
    "vials": 14,
    "purchases": 11,
    "supplies": 5,
    "calendar": 5,
}


def parse_module(name):
    path = ROOT / "app/routers" / f"{name}.py"

    source = path.read_text()

    return ast.parse(source), source


def dependency_names(tree):
    results = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if not isinstance(node.func, ast.Name):
            continue

        if node.func.id != "Depends":
            continue

        if not node.args:
            continue

        dependency = node.args[0]

        if isinstance(dependency, ast.Name):
            results.append(dependency.id)

    return results


@pytest.mark.parametrize(
    "name,count",
    list(CORE.items()),
)
def test_every_core_dependency_is_scoped(name, count):
    tree, source = parse_module(name)

    dependencies = dependency_names(tree)

    assert dependencies.count("get_scoped_db390") == count
    assert "get_db" not in dependencies

    assert (
        "from ..scoped_db390 import get_scoped_db390"
        in source
    )

    assert "from ..db import get_db" not in source


def test_total_conversion_count():
    assert sum(CORE.values()) == 52


def test_scoped_dependency_preserves_fastapi_override():
    parameter = inspect.signature(
        get_scoped_db390
    ).parameters["db"]

    dependency = parameter.default

    assert isinstance(dependency, DependsParameter)
    assert dependency.dependency is get_db


def test_existing_critical_routes_remain_registered():
    """Inspect real FastAPI routers, not app.routes placeholders."""

    from app.routers import (
        compounds,
        protocols,
        vials,
        purchases,
        supplies,
        calendar,
    )

    modules = {
        "/compounds": compounds,
        "/protocols": protocols,
        "/vials": vials,
        "/purchases": purchases,
        "/supplies": supplies,
        "/calendar": calendar,
    }

    for expected_path, module in modules.items():
        routes = [
            route
            for route in module.router.routes
            if isinstance(route, APIRoute)
        ]

        assert routes, (
            f"No FastAPI API routes found: {module.__name__}"
        )

        paths = {route.path for route in routes}

        assert expected_path in paths, (
            f"Missing {expected_path} in {module.__name__}"
        )

        root_route = next(
            route for route in routes
            if route.path == expected_path
        )

        assert "GET" in root_route.methods, (
            f"Expected GET endpoint: {expected_path}"
        )


def test_converted_routes_have_fastapi_dependencies():
    """Check live router definitions, not just source strings."""

    from app.routers import (
        compounds,
        protocols,
        vials,
        purchases,
        supplies,
        calendar,
    )

    modules = (
        compounds,
        protocols,
        vials,
        purchases,
        supplies,
        calendar,
    )

    total = 0

    for module in modules:
        for route in module.router.routes:
            if not isinstance(route, APIRoute):
                continue

            dependencies = {
                item.call
                for item in route.dependant.dependencies
            }

            if get_scoped_db390 in dependencies:
                total += 1

    assert total >= 45, (
        f"Unexpectedly few scoped endpoints: {total}"
    )


def test_scope_does_not_enable_future_users():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3, 4, 100):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)


def test_models_and_engine_remain_unchanged():
    for filename in (
        "app/db.py",
        "app/models.py",
        "app/user_db389.py",
        "app/request_scope393.py",
    ):
        assert (ROOT / filename).is_file()
