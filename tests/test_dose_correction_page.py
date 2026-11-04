"""Dose correction page title, audit history and supply entry contracts."""

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "app/templates/dose_edit.html"
ROUTER = ROOT / "app/routers/doses.py"
BACKEND = ROOT / "app/manual_supplies.py"


def test_title_contains_no_audit_markup():
    source = HTML.read_text()

    assert source.startswith(
        '{% extends "base.html" %}'
        '{% block title %}Edit dose{% endblock %}'
        '{% block content %}'
    )

    title, body = source.split(
        '{% block content %}', 1
    )

    assert "<section" not in title
    assert "Change history" not in title

    assert body.count(
        '<section class="card wide" aria-label="Change history">'
    ) == 1
    assert body.count('{% for event in history %}') == 1
    assert body.count('{% else %}<p>No corrections recorded.</p>') == 1

    Environment().parse(source)


def test_existing_edit_fields_and_audit_history_remain():
    source = HTML.read_text()

    for marker in (
        'action="/doses/{{ dose.id }}/edit"',
        'name="taken_at"',
        'name="amount"',
        'name="unit"',
        'name="kind"',
        'name="site"',
        'name="notes"',
        'name="supply_id_used"',
        'name="supply_qty_{{ s.id }}"',
        'value="{{ used.get(s.id,1) }}"',
        'event.before_json | from_json',
        'event.after_json | from_json',
    ):
        assert marker in source, marker


def test_counted_categories_come_from_database():
    source = ROUTER.read_text()

    assert 'SupplyCategory.unit == "count"' in source
    assert "counted_supply_kinds=counted_supply_kinds" in source


def test_correction_quantity_field_renders_both_units():
    source = HTML.read_text()

    marker = '<input aria-label="Quantity of {{ s.name }} used '
    assert source.count(marker) == 1

    start = source.index(marker)
    end = source.index(">", start) + 1

    fragment = Environment(autoescape=True).from_string(
        source[start:end]
    )

    counted = fragment.render(
        s=SimpleNamespace(
            id=10, name="Needle", kind="needle"
        ),
        counted_supply_kinds={"needle", "syringe"},
        used={10: 2},
    )
    assert 'data-counted="true"' in counted
    assert 'min="1"' in counted
    assert 'step="1"' in counted
    assert 'value="2"' in counted
    assert "whole items" in counted

    volume = fragment.render(
        s=SimpleNamespace(
            id=11, name="BAC water", kind="bac_water"
        ),
        counted_supply_kinds={"needle", "syringe"},
        used={11: 0.5},
    )
    assert 'data-counted="false"' in volume
    assert 'min="0.001"' in volume
    assert 'step="any"' in volume
    assert 'value="0.5"' in volume
    assert "fractional quantities allowed" in volume


def test_correction_inventory_and_audit_protections():
    source = ROUTER.read_text()

    assert "reserve_inventory_write" in source
    assert "manual_supplies.selections(" in source
    assert "credits={u.supply_id:u.amount" in source
    assert 'action="edit"' in source
    assert "db.commit()" in source

    backend = BACKEND.read_text()
    assert 'cat.unit == "count"' in backend
    assert "not qty.is_integer()" in backend
    assert "Selected supplies exceed available stock." in backend
