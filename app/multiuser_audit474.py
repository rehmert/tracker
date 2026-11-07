"""Release 474: read-only DEV multi-user cutover auditor.

Static source analysis is deliberately conservative.
It cannot establish behavioral security or feature parity.
The only purpose is to produce evidence and identify
known blockers before a broader activation is attempted.

No database is opened or modified. No HTTP server is started.
"""
import argparse
import ast
import json
from pathlib import Path


ROOT474 = Path(__file__).resolve().parents[1]


def _source474(root, relative):
    path = root / relative
    if not path.is_file():
        raise RuntimeError(
            "Required source unavailable: " + relative
        )
    text = path.read_text(encoding="utf-8")
    return text, ast.parse(text, filename=relative)


def _functions474(tree):
    return {
        node.name
        for node in tree.body
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        )
    }


def _calls474(tree, name):
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == name
    ]


def _route_inventory474(root):
    directory = root / "app" / "routers"
    if not directory.is_dir():
        raise RuntimeError("Feature router directory missing")

    routes = []
    methods = {
        "get", "post", "put", "patch", "delete",
        "options", "head",
    }

    for path in sorted(directory.glob("*.py")):
        relative = str(path.relative_to(root))
        _, tree = _source474(root, relative)

        for node in ast.walk(tree):
            if not isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                continue

            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue

                target = decorator.func

                if not (
                    isinstance(target, ast.Attribute)
                    and target.attr in methods
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "router"
                    and decorator.args
                    and isinstance(
                        decorator.args[0], ast.Constant
                    )
                    and isinstance(
                        decorator.args[0].value, str
                    )
                ):
                    continue

                routes.append({
                    "module": relative,
                    "method": target.attr.upper(),
                    "path": decorator.args[0].value,
                    "handler": node.name,
                })

    if not routes:
        raise RuntimeError(
            "No primary application routes discovered"
        )

    return sorted(
        routes,
        key=lambda item: (
            item["module"], item["path"],
            item["method"], item["handler"],
        ),
    )


def _secondary_routes474(root):
    _, tree = _source474(
        root, "app/secondary_preview430.py"
    )

    routes = []
    for node in ast.walk(tree):
        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue

        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue

            target = decorator.func
            if not (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "preview_app"
                and target.attr in (
                    "get", "post", "put",
                    "patch", "delete",
                )
                and decorator.args
                and isinstance(
                    decorator.args[0], ast.Constant
                )
                and isinstance(
                    decorator.args[0].value, str
                )
            ):
                continue

            routes.append({
                "method": target.attr.upper(),
                "path": "/secondary" + decorator.args[0].value,
                "handler": node.name,
            })

    if not routes:
        raise RuntimeError("Secondary routes unavailable")

    return sorted(
        routes,
        key=lambda row: (
            row["path"], row["method"], row["handler"]
        ),
    )


def _has_admin_equality474(tree):
    """Check that require_auth explicitly checks for user 1."""
    fn = next(
        (
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "require_auth"
        ),
        None,
    )
    if fn is None:
        return False

    for node in ast.walk(fn):
        if not isinstance(node, ast.Compare):
            continue
        if any(
            isinstance(part, ast.Constant)
            and type(part.value) is int
            and part.value == 1
            for part in (
                node.left, *node.comparators,
            )
        ):
            return True

    return False


def audit474(root=ROOT474):
    root = Path(root).resolve()

    sources = {}
    trees = {}

    required = (
        "app/main.py",
        "app/security.py",
        "app/request_scope393.py",
        "app/scoped_db390.py",
        "app/workspace_engine401.py",
        "app/food_storage_guard391.py",
        "app/secondary_preview430.py",
        "app/secondary_request_db467.py",
        "app/secondary_orm468.py",
        "app/secondary_files472.py",
        "app/unified_login473.py",
        "app/routers/session_login385.py",
    )

    for relative in required:
        sources[relative], trees[relative] = (
            _source474(root, relative)
        )

    primary = _route_inventory474(root)
    secondary = _secondary_routes474(root)

    checks = {
        "primary_auth_requires_admin_identity":
            _has_admin_equality474(
                trees["app/security.py"]
            ),
        "request_scope_rejects_secondary_identity":
            "Additional users remain disabled"
            in sources["app/request_scope393.py"],
        "workspace_engine_rejects_secondary":
            "Additional workspace engines disabled"
            in sources["app/workspace_engine401.py"],
        "global_food_engine_guard_present":
            "administrator_engine"
            in sources["app/food_storage_guard391.py"],
        "unified_login_explicitly_dev_gated":
            "TRACKER_MULTIUSER_LOGIN473"
            in sources["app/unified_login473.py"],
        "secondary_preview_explicitly_dev_gated":
            "TRACKER_SECONDARY_PREVIEW430"
            in sources["app/secondary_preview430.py"],
        "private_request_scope_exists":
            "verified_private_scope467"
            in _functions474(
                trees["app/secondary_request_db467.py"]
            ),
        "private_sqlalchemy_reader_exists":
            "private_orm468"
            in _functions474(
                trees["app/secondary_orm468.py"]
            ),
        "private_upload_gate_exists":
            "TRACKER_SECONDARY_ATTACHMENT_UPLOAD472"
            in sources["app/secondary_files472.py"],
        "normal_login_secondary_path_exists":
            "authenticate_secondary473"
            in sources["app/routers/session_login385.py"],
    }

    if not all(checks.values()):
        raise RuntimeError(
            "Expected isolation boundary changed: "
            + ", ".join(
                key for key, passed in checks.items()
                if not passed
            )
        )

    primary_modules = sorted({
        route["module"] for route in primary
    })

    # This is a source-level indicator, not proof of
    # unauthorized database access.
    global_references = []
    for relative in primary_modules:
        source, _ = _source474(root, relative)
        if any(marker in source for marker in (
            "from ..db import engine",
            "from ..db import get_db",
            "from ..db import SessionLocal",
        )):
            global_references.append(relative)

    blockers = [
        {
            "id": "ADMIN_ONLY_SCOPE",
            "module": "app/request_scope393.py",
            "description":
                "Normal authenticated request scope still "
                "rejects users other than administrator 1",
        },
        {
            "id": "ADMIN_ONLY_ENGINE",
            "module": "app/workspace_engine401.py",
            "description":
                "Normal live SQLAlchemy session resolution "
                "still authorizes administrator storage only",
        },
        {
            "id": "FOOD_GLOBAL_ENGINE",
            "module": "app/food_storage_guard391.py",
            "description":
                "Primary food routes still depend on "
                "the process-wide administrator engine",
        },
        {
            "id": "ROUTE_PARITY_NOT_PROVEN",
            "module": "app/main.py",
            "description":
                "Private pilot endpoints do not establish "
                "equivalence with every primary feature route",
        },
    ]

    return {
        "schema": "tracker-multiuser-cutover-audit474",
        "source_only": True,
        "full_main_app_cutover_ready": False,
        "secondary_pilot_isolation_expected": True,
        "runtime_security_proven": False,
        "primary_route_count": len(primary),
        "secondary_route_count": len(secondary),
        "primary_router_module_count": len(primary_modules),
        "primary_modules_with_direct_db_imports":
            global_references,
        "checks": checks,
        "blocking_items": blockers,
        "primary_routes": primary,
        "secondary_routes": secondary,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Read-only multi-user cutover audit"
    )
    parser.add_argument(
        "--require-full-cutover",
        action="store_true",
        help="Exit nonzero while full main-app cutover is blocked",
    )
    args = parser.parse_args()

    result = audit474()
    print(json.dumps(result, indent=2, sort_keys=True))

    if (
        args.require_full_cutover
        and not result["full_main_app_cutover_ready"]
    ):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
