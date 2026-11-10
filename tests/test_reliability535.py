"""Release 535: Lab and Purchase test fixture override isolation."""

import ast
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch


ROOT = Path(__file__).resolve().parents[1]

CASES = (
    ("test_lab_csv_portability.py", "lab_client"),
    ("test_lab_compare_review.py", "compare_client"),
    ("test_labs_overview.py", "lab_overview_client"),
    ("test_purchase_history_review.py", "purchase_history_client"),
)


@pytest.mark.parametrize("filename,fixture", CASES)
def test_fixture_restores_existing_database_override535(
    filename, fixture,
):
    """No fixture may discard an override owned by another test."""
    path = ROOT / "tests" / filename
    source = path.read_text()

    tree = ast.parse(source, filename=str(path))

    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == fixture
    ]

    assert len(functions) == 1
    node = functions[0]

    assert "monkeypatch" in {
        arg.arg for arg in node.args.args
    }

    body = ast.get_source_segment(source, node)
    assert body is not None

    assert (
        "monkeypatch.setitem("
        "app.dependency_overrides, get_db,"
    ) in body

    assert (
        "app.dependency_overrides.pop(get_db"
        not in body
    )

    assert (
        "app.dependency_overrides[get_db] ="
        not in body
    )

    assert "engine.dispose()" in body


def test_preexisting_dependency_survives_cleanup535():
    key = object()
    previous = object()
    replacement = object()
    overrides = {key: previous}

    with MonkeyPatch.context() as patch:
        patch.setitem(overrides, key, replacement)
        assert overrides[key] is replacement

    assert overrides[key] is previous


def test_no_preexisting_dependency_remains_absent535():
    key = object()
    overrides = {}

    with MonkeyPatch.context() as patch:
        patch.setitem(overrides, key, object())
        assert key in overrides

    assert key not in overrides


def test_nested_database_override_cleanup535():
    key = object()
    original = object()
    outer_value = object()
    inner_value = object()

    overrides = {key: original}

    with MonkeyPatch.context() as outer:
        outer.setitem(overrides, key, outer_value)

        with MonkeyPatch.context() as inner:
            inner.setitem(overrides, key, inner_value)
            assert overrides[key] is inner_value

        assert overrides[key] is outer_value

    assert overrides[key] is original


def test_cleanup_on_test_exception535():
    key = object()
    original = object()
    overrides = {key: original}

    with pytest.raises(ValueError, match="synthetic"):
        with MonkeyPatch.context() as patch:
            patch.setitem(overrides, key, object())
            raise ValueError("synthetic")

    assert overrides[key] is original


@pytest.mark.parametrize("filename,fixture", CASES)
def test_fixture_uses_function_scope535(filename, fixture):
    """The restoring patch must not outlive a test function."""
    path = ROOT / "tests" / filename
    tree = ast.parse(path.read_text())

    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == fixture
    ]

    assert len(nodes) == 1
    decorators = nodes[0].decorator_list

    assert len(decorators) == 1
    assert (
        isinstance(decorators[0], ast.Attribute)
        and isinstance(decorators[0].value, ast.Name)
        and decorators[0].value.id == "pytest"
        and decorators[0].attr == "fixture"
    )
