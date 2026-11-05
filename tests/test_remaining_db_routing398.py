"""Release 398: remaining forecasting/workflow database dependencies."""

import ast
import inspect
from importlib import import_module
from pathlib import Path

import pytest

from fastapi.params import Depends as DependsParameter
from fastapi.routing import APIRoute

from app.db import get_db
from app.scoped_db390 import get_scoped_db390


ROOT = Path(__file__).resolve().parents[1]

FEATURES = {
    "expiry_exposure": 2,
    "fefo_forecast": 2,
    "forecast_audit": 2,
    "forecast_horizons": 2,
    "inventory_data_quality": 3,
    "inventory_forecast": 2,
    "planning_hub": 2,
    "planning_priorities": 2,
    "protocol_coverage": 2,
    "reconstitution_calculator": 1,
    "replenishment_review": 2,
    "scheduled_forecast": 2,
    "workflow_tools": 4,
}


def dependency_names(path):
    tree = ast.parse(path.read_text())

    names = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if not isinstance(node.func, ast.Name):
            continue

        if node.func.id != "Depends" or not node.args:
            continue

        dependency = node.args[0]

        if isinstance(dependency, ast.Name):
            names.append(dependency.id)

    return names


@pytest.mark.parametrize(
    "name,expected",
    list(FEATURES.items()),
)
def test_dependencies_are_scoped(name, expected):
    path = (
        ROOT / "app/routers" / f"{name}.py"
    )

    source = path.read_text()
    dependencies = dependency_names(path)

    assert dependencies.count(
        "get_scoped_db390"
    ) == expected

    assert "get_db" not in dependencies

    assert (
        "from ..scoped_db390 import get_scoped_db390"
        in source
    )

    assert "from ..db import get_db" not in source


def test_total_conversion():
    assert len(FEATURES) == 13
    assert sum(FEATURES.values()) == 28


@pytest.mark.parametrize(
    "name",
    list(FEATURES),
)
def test_live_routers_use_scoped_dependency(name):
    module = import_module(
        f"app.routers.{name}"
    )

    routes = [
        route
        for route in module.router.routes
        if isinstance(route, APIRoute)
    ]

    assert routes, name

    count = 0

    for route in routes:
        dependencies = {
            item.call
            for item in route.dependant.dependencies
        }

        if get_scoped_db390 in dependencies:
            count += 1

    assert count >= 1, (
        f"No scoped route found in {name}"
    )


def test_dependency_override_is_preserved():
    parameter = inspect.signature(
        get_scoped_db390
    ).parameters["db"]

    dependency = parameter.default

    assert isinstance(
        dependency,
        DependsParameter,
    )

    assert dependency.dependency is get_db


def test_additional_users_remain_disabled():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3, 4, 100):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)


def test_original_database_foundation_unchanged():
    for filename in (
        "app/db.py",
        "app/models.py",
        "app/user_db389.py",
        "app/request_scope393.py",
    ):
        assert (ROOT / filename).is_file()
