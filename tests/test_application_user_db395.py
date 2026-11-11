"""Release 395: shared database routing across application features."""

import ast
import inspect
from pathlib import Path

import pytest

from fastapi.params import Depends as DependsParameter
from fastapi.routing import APIRoute

from app.db import get_db
from app.scoped_db390 import get_scoped_db390


ROOT = Path(__file__).resolve().parents[1]

FEATURES = {
    "pk": 53,
    "vendor_prices": 18,
    "blends": 9,
    "pages": 12,
    "reliability": 7,
    "search": 1,
    "inventory_intelligence": 2,
    "health_timeline": 2,
    "health_insights": 1,
    "exports": 1,
    "activity": 1,
    "inventory_timeline": 1,
}


def source_dependency_counts(name):
    path = ROOT / "app/routers" / f"{name}.py"
    source = path.read_text()

    tree = ast.parse(
        source,
        filename=str(path),
    )

    scoped = 0
    legacy = 0

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if not isinstance(node.func, ast.Name):
            continue

        if node.func.id != "Depends":
            continue

        if not node.args:
            continue

        target = node.args[0]

        if not isinstance(target, ast.Name):
            continue

        if target.id == "get_scoped_db390":
            scoped += 1

        if target.id == "get_db":
            legacy += 1

    return scoped, legacy, source


@pytest.mark.parametrize(
    "name,expected",
    list(FEATURES.items()),
)
def test_feature_database_dependencies_are_scoped(
    name,
    expected,
):
    scoped, legacy, source = source_dependency_counts(name)

    assert scoped == expected
    assert legacy == 0

    assert (
        "from ..scoped_db390 import get_scoped_db390"
        in source
    )

    assert "from ..db import get_db" not in source


def test_total_converted_dependencies():
    assert len(FEATURES) == 12
    assert sum(FEATURES.values()) == 108


def test_fastapi_override_compatibility():
    parameter = inspect.signature(
        get_scoped_db390
    ).parameters["db"]

    dependency = parameter.default

    assert isinstance(dependency, DependsParameter)
    assert dependency.dependency is get_db


@pytest.mark.parametrize(
    "name",
    list(FEATURES),
)
def test_live_feature_router_exposes_scoped_dependencies(name):
    """Use each router directly, avoiding app.routes placeholders."""

    from importlib import import_module

    module = import_module(
        f"app.routers.{name}"
    )

    routes = [
        route
        for route in module.router.routes
        if isinstance(route, APIRoute)
    ]

    assert routes, f"No FastAPI routes found in {name}"

    scoped_routes = []

    for route in routes:
        dependencies = {
            item.call
            for item in route.dependant.dependencies
        }

        if get_scoped_db390 in dependencies:
            scoped_routes.append(route.path)

    assert scoped_routes, (
        f"No authenticated DB routes found in {name}"
    )


def test_future_users_remain_inactive():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3, 4, 100):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)


def test_original_database_engine_preserved():
    for filename in (
        "app/db.py",
        "app/models.py",
        "app/user_db389.py",
        "app/request_scope393.py",
    ):
        assert (ROOT / filename).is_file()


def test_filesystem_isolation_not_marked_complete():
    from app.user_storage388 import planned_storage

    second = planned_storage(2)

    assert second.mode == "reserved-inactive"
    assert second.user_id == 2
    assert not second.database.exists()
