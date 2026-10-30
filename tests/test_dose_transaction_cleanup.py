"""Regression checks for dose transaction cleanup."""

import ast
from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "routers"
    / "doses.py"
)


def _create_dose_function():
    tree = ast.parse(SOURCE.read_text())

    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef):
            if node.name == "create_dose":
                return node

    raise AssertionError("create_dose not found")


def test_dose_creation_has_rollback_helper():
    function = _create_dose_function()

    helpers = [
        node
        for node in function.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "reject_dose"
    ]

    assert len(helpers) == 1

    helper = helpers[0]

    calls = [
        node
        for node in ast.walk(helper)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "rollback"
    ]

    assert calls, "Validation helper must roll back."


def test_dose_validation_uses_cleanup_helper():
    function = _create_dose_function()

    direct_error_returns = []

    for node in ast.walk(function):
        if not isinstance(node, ast.Return):
            continue

        call = node.value

        if not isinstance(call, ast.Call):
            continue

        if isinstance(call.func, ast.Name):
            if call.func.id == "_error":
                # The helper itself is allowed to call _error.
                direct_error_returns.append(node)

    # Exactly one direct _error return, inside reject_dose.
    assert len(direct_error_returns) == 1


def test_dose_creation_preserves_transaction_commit():
    function = _create_dose_function()

    commits = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "commit"
    ]

    assert commits, "Dose creation must commit successful writes."
