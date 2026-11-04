"""Vial preparation supply fields reflect configured category units."""

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "app/templates/vial_detail.html"
ROUTER = ROOT / "app/routers/vials.py"
BACKEND = ROOT / "app/manual_supplies.py"


def test_category_metadata_is_database_derived():
    source = ROUTER.read_text()

    assert "SupplyCategory" in source
    assert 'SupplyCategory.unit == "count"' in source
    assert "counted_supply_kinds=counted_supply_kinds" in source


def test_both_preparation_forms_use_category_rules():
    source = HTML.read_text()

    assert source.count(
        'name="supply_qty_{{ s.id }}"'
    ) == 2

    assert source.count(
        "s.kind in counted_supply_kinds"
    ) >= 8

    assert source.count('data-counted="') == 2
    assert source.count(
        'min="{{ \'1\' if s.kind in counted_supply_kinds '
        'else \'0.001\' }}"'
    ) == 2

    assert source.count(
        'step="{{ \'1\' if s.kind in counted_supply_kinds '
        'else \'any\' }}"'
    ) == 2

    Environment().parse(source)


def test_rendered_input_for_counted_supply():
    source = HTML.read_text()

    marker = '<input aria-label="Quantity of {{ s.name }} used '
    assert source.count(marker) == 2

    start = source.index(marker)
    end = source.index(">", start) + 1

    fragment = Environment(
        autoescape=True
    ).from_string(source[start:end])

    counted = fragment.render(
        s=SimpleNamespace(
            id=101, name="Syringe", kind="syringe"
        ),
        counted_supply_kinds={"syringe", "needle"},
    )
    assert 'min="1"' in counted
    assert 'step="1"' in counted
    assert 'data-counted="true"' in counted
    assert "whole items" in counted

    volume = fragment.render(
        s=SimpleNamespace(
            id=102, name="BAC water", kind="bac_water"
        ),
        counted_supply_kinds={"syringe", "needle"},
    )
    assert 'min="0.001"' in volume
    assert 'step="any"' in volume
    assert 'data-counted="false"' in volume
    assert "fractional quantities allowed" in volume


def test_vial_preparation_workflows_preserved():
    source = HTML.read_text()

    assert 'action="/vials/{{ v.id }}/reconstitute"' in source
    assert 'action="/vials/{{ v.id }}/filter"' in source
    assert source.count('name="supply_id_used"') == 2
    assert source.count(
        '{% for s in disposable_supplies %}'
    ) == 2


def test_backend_remains_authoritative():
    source = BACKEND.read_text()

    assert 'cat.unit == "count"' in source
    assert "not qty.is_integer()" in source
    assert "Selected supplies exceed available stock." in source

    router = ROUTER.read_text()

    assert "reserve_inventory_write" in router
    assert "manual_supplies" in router
