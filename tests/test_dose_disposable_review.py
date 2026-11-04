"""Dose final review shows selected supply quantities without writing data."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "app/static/js/tracker-dose-final-review.js"
TEMPLATE = ROOT / "app/templates/doses.html"


def test_each_selected_supply_has_name_and_quantity():
    source = JS.read_text()

    assert 'checkbox.closest("tr")' in source
    assert 'querySelectorAll("td")[1]' in source
    assert '"supply_qty_" + checkbox.value' in source
    assert 'item.name + " × "' in source
    assert '["Disposables", supplyDescription]' in source


def test_invalid_supply_quantities_are_flagged():
    source = JS.read_text()

    assert "const invalid = !quantity" in source
    assert "!Number.isFinite(numeric) || numeric <= 0" in source
    assert "const invalidSupplies = supplies.filter" in source
    assert "if (invalidSupplies.length)" in source
    assert "panel.dataset.reviewState = missing.length" in source


def test_review_refreshes_after_success():
    source = JS.read_text()

    assert '"tracker:dose-saved"' in source
    assert "queueMicrotask(render)" in source
    assert 'form.addEventListener("input", render)' in source
    assert 'form.addEventListener("change", render)' in source


def test_review_remains_read_only():
    source = JS.read_text()

    for forbidden in (
        "fetch(",
        "requestSubmit(",
        "form.submit(",
        "localStorage.",
        "sessionStorage.",
    ):
        assert forbidden not in source

    assert "description.textContent = content" in source


def test_template_and_backend_contracts():
    template = TEMPLATE.read_text()

    assert "tracker-dose-final-review.js?v=20261103d" in template
    assert 'name="supply_id_used"' in template
    assert 'name="supply_qty_{{ s.id }}"' in template

    Environment().parse(template)

    backend = (ROOT / "app/routers/doses.py").read_text()

    assert "idempotency.check(" in backend
    assert "reserve_inventory_write" in backend
    assert "manual_supplies.deduct(" in backend
