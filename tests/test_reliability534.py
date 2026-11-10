"""Release 534: restoring database overrides and coherent fixture timestamps."""

import ast
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "filename,fixture",
    [
        ("test_health_timeline_filters.py", "timeline_records"),
        ("test_supply_consumption_review.py", "consumption_client"),
    ],
)
def test_database_fixture_uses_restoring_override534(filename, fixture):
    path = ROOT / "tests" / filename
    source = path.read_text()

    tree = ast.parse(source, filename=str(path))
    matches = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == fixture
    ]

    assert len(matches) == 1
    node = matches[0]

    assert "monkeypatch" in {
        arg.arg for arg in node.args.args
    }

    body = ast.get_source_segment(source, node)
    assert body is not None

    assert "monkeypatch.setitem(" in body
    assert "app.dependency_overrides, get_db" in body
    assert "app.dependency_overrides.pop(get_db" not in body
    assert "app.dependency_overrides[get_db] =" not in body
    assert "engine.dispose()" in body


def test_existing_override_survives_fixture_style_cleanup534():
    key = object()
    previous = object()
    temporary = object()
    overrides = {key: previous}

    with MonkeyPatch.context() as patch:
        patch.setitem(overrides, key, temporary)
        assert overrides[key] is temporary

    assert overrides[key] is previous


def test_missing_override_is_removed_after_cleanup534():
    key = object()
    overrides = {}

    with MonkeyPatch.context() as patch:
        patch.setitem(overrides, key, object())
        assert key in overrides

    assert key not in overrides


def test_nested_override_restoration534():
    key = object()
    original = object()
    overrides = {key: original}

    with MonkeyPatch.context() as outer:
        first = object()
        outer.setitem(overrides, key, first)

        with MonkeyPatch.context() as inner:
            second = object()
            inner.setitem(overrides, key, second)
            assert overrides[key] is second

        assert overrides[key] is first

    assert overrides[key] is original


def test_health_timeline_fixture_uses_one_clock_read534():
    path = ROOT / "tests/test_health_timeline_filters.py"
    tree = ast.parse(path.read_text())

    fixture = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "timeline_records"
    )

    calls = [
        node for node in ast.walk(fixture)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "date"
        and node.func.attr == "today"
    ]

    assert len(calls) == 1


def test_supply_fixture_uses_one_timestamp534():
    path = ROOT / "tests/test_supply_consumption_review.py"
    source = path.read_text()
    tree = ast.parse(source)

    seed = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "seed_consumption"
    )

    body = ast.get_source_segment(source, seed)
    assert body is not None

    calls = [
        node for node in ast.walk(seed)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "datetime"
        and node.func.attr == "now"
    ]

    assert len(calls) == 1
    assert "recorded_at = datetime.now() - timedelta(days=1)" in body
    assert body.count("created_at=recorded_at") == 2


def test_restoration_on_exception534():
    key = object()
    existing = object()
    overrides = {key: existing}

    with pytest.raises(RuntimeError, match="synthetic"):
        with MonkeyPatch.context() as patch:
            patch.setitem(overrides, key, object())
            raise RuntimeError("synthetic")

    assert overrides[key] is existing
