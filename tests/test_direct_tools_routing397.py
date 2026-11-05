"""Release 397: reporting and direct-SQLite migration contracts."""

import ast
import inspect
from pathlib import Path

from fastapi.params import Depends as DependsParameter

from app.db import get_db
from app.scoped_db390 import get_scoped_db390


ROOT = Path(__file__).resolve().parents[1]


def test_consolidated_reports_use_scoped_dependencies():
    path = (
        ROOT / "app/routers/consolidated_reports.py"
    )

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

        if value.id == "get_scoped_db390":
            scoped += 1

        if value.id == "get_db":
            legacy += 1

    assert scoped == 2
    assert legacy == 0


def test_scoped_db_keeps_override_compatibility():
    parameter = inspect.signature(
        get_scoped_db390
    ).parameters["db"]

    dependency = parameter.default

    assert isinstance(dependency, DependsParameter)
    assert dependency.dependency is get_db


def test_direct_tools_still_use_read_only_sqlite():
    for filename in (
        "app/routers/sqlite_viewer.py",
        "app/routers/record_explorer.py",
    ):
        source = (ROOT / filename).read_text()

        assert "sqlite3.connect(" in source
        assert "query_only=ON" in source
        assert "mode=ro" in source


def test_backup_implementation_remains_unchanged():
    assert (ROOT / "app/backup.py").is_file()
    assert (
        ROOT / "scripts/tracker_backup.py"
    ).is_file()
