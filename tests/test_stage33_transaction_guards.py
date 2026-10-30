"""Regression checks for inventory write reservation ordering."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app" / "routers"


def test_mutating_routes_reserve_before_first_database_read():

    targets = {
        "compounds.py": {
            "create_compound",
            "delete_compound",
            "update_compound",
        },
        "supplies.py": {
            "add",
            "use",
            "log_pill",
            "create_category",
        },
        "blends.py": {
            "create_blend",
            "record_blend_dose",
        },
    }

    for filename, names in targets.items():

        source = (ROOT / filename).read_text()
        tree = ast.parse(source)

        found = set()

        for node in tree.body:

            if not isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                continue

            if node.name not in names:
                continue

            found.add(node.name)

            statements = ast.get_source_segment(source, node)

            assert "reserve_inventory_write(db)" in statements, (
                filename,
                node.name,
            )

            reserve = statements.index(
                "reserve_inventory_write(db)"
            )

            lookups = [
                statements.find(x)
                for x in (
                    "db.get(",
                    "db.scalar(",
                    "db.scalars(",
                    "db.query(",
                    "db.execute(",
                )
            ]

            lookups = [x for x in lookups if x >= 0]

            assert not lookups or reserve < min(lookups), (
                filename,
                node.name,
            )

        assert found == names, (
            filename,
            names - found,
        )
