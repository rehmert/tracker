"""Dose disposable quantities reflect the configured category unit."""

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/doses.html"
ROUTER = ROOT / "app/routers/doses.py"
BACKEND = ROOT / "app/manual_supplies.py"


def test_counted_quantities_use_integer_steps():
    source = TEMPLATE.read_text()
    assert "s.kind in counted_supply_kinds" in source

    assert (
        'min="{{ \'1\' if s.kind in counted_supply_kinds else \'0.001\' }}"'
        in source
    )
    assert (
        'step="{{ \'1\' if s.kind in counted_supply_kinds else \'any\' }}"'
        in source
    )


def test_quantity_field_rendering_for_each_unit():
    source = TEMPLATE.read_text()

    start = source.index(
        '<input aria-label="Quantity of {{ s.name }} used '
    )
    end = source.index(">", start) + 1
    fragment = source[start:end]

    template = Environment(autoescape=True).from_string(fragment)

    counted = template.render(
        s=SimpleNamespace(id=12, name="Syringe", kind="syringe"),
        counted_supply_kinds={"syringe", "needle"},
    )
    assert 'min="1"' in counted
    assert 'step="1"' in counted
    assert 'data-counted="true"' in counted
    assert "whole items" in counted

    fractional = template.render(
        s=SimpleNamespace(id=13, name="BAC water", kind="bac_water"),
        counted_supply_kinds={"syringe", "needle"},
    )
    assert 'min="0.001"' in fractional
    assert 'step="any"' in fractional
    assert 'data-counted="false"' in fractional
    assert "fractional quantities allowed" in fractional


def test_category_units_still_come_from_database():
    router = ROUTER.read_text()
    assert 'SupplyCategory.unit == "count"' in router
    assert "counted_supply_kinds=counted_supply_kinds" in router

    backend = BACKEND.read_text()
    assert 'cat.unit == "count"' in backend
    assert "not qty.is_integer()" in backend


def test_existing_review_is_preserved():
    source = TEMPLATE.read_text()

    assert 'id="tracker-dose-final-review"' in source
    assert 'id="tracker-dose-review-first-issue"' in source
    assert "tracker-dose-final-review.js?v=20261103e" in source
    assert 'name="supply_id_used"' in source

    Environment().parse(source)


def test_no_change_to_recording_safeguards():
    source = (ROOT / "app/routers/doses.py").read_text()

    assert "idempotency.check(" in source
    assert "reserve_inventory_write" in source
    assert "manual_supplies.deduct(" in source
