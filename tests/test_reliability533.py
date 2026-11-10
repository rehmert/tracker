"""Release 533: existing dependency overrides survive fixture cleanup.

These tests do not use a live application database or network.
"""

import ast
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "filename,fixture",
    [
        ("test_vitals_range_ux.py", "vitals_client"),
        (
            "test_health_timeline_active_protocols.py",
            "timeline_client",
        ),
        (
            "test_inventory_alert_csv_review.py",
            "alert_client",
        ),
    ],
)
def test_fixture_uses_restoring_patch533(filename, fixture):
    path = ROOT / "tests" / filename
    source = path.read_text()

    tree = ast.parse(source, filename=str(path))
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == fixture
    ]

    assert len(nodes) == 1
    node = nodes[0]

    assert "monkeypatch" in [
        arg.arg for arg in node.args.args
    ]

    fixture_source = ast.get_source_segment(source, node)
    assert fixture_source is not None

    assert (
        "monkeypatch.setitem("
        "app.dependency_overrides, get_db,"
    ) in fixture_source

    assert (
        "app.dependency_overrides.pop(get_db"
        not in fixture_source
    )


def test_existing_override_restored533():
    """setitem restores an existing value, not just absent keys."""
    key = object()
    prior = object()
    temporary = object()

    overrides = {key: prior}

    with MonkeyPatch.context() as patch:
        patch.setitem(overrides, key, temporary)
        assert overrides[key] is temporary

    assert overrides[key] is prior


def test_absent_override_restored533():
    key = object()
    temporary = object()
    overrides = {}

    with MonkeyPatch.context() as patch:
        patch.setitem(overrides, key, temporary)
        assert overrides[key] is temporary

    assert key not in overrides


def test_nested_overrides_restore_in_order533():
    key = object()
    original = object()
    first = object()
    second = object()

    overrides = {key: original}

    with MonkeyPatch.context() as outer:
        outer.setitem(overrides, key, first)

        with MonkeyPatch.context() as inner:
            inner.setitem(overrides, key, second)
            assert overrides[key] is second

        assert overrides[key] is first

    assert overrides[key] is original


def test_override_restored_after_exception533():
    key = object()
    original = object()
    overrides = {key: original}

    with pytest.raises(RuntimeError, match="synthetic"):
        with MonkeyPatch.context() as patch:
            patch.setitem(overrides, key, object())
            raise RuntimeError("synthetic")

    assert overrides[key] is original


def test_health_timeline_uses_one_reference_date533():
    path = ROOT / "tests/test_health_timeline_active_protocols.py"
    source = path.read_text()

    tree = ast.parse(source, filename=str(path))

    target = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name.startswith(
            "test_timeline_only_includes_active_protocols"
        )
    ]

    assert len(target) == 1
    text = ast.get_source_segment(source, target[0])
    assert text is not None

    assert text.count("date.today()") == 1
    assert "today = date.today()" in text
    assert "start = today - timedelta(days=8)" in text
    assert "end = today - timedelta(days=2)" in text
