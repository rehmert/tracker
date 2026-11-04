"""Read-only supply availability checks during dose review."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "app/static/js/tracker-dose-final-review.js"
HTML = ROOT / "app/templates/doses.html"


def test_availability_comes_from_existing_supply_row():
    script = JS.read_text()

    assert 'querySelectorAll("td")[2]' in script
    assert 'available.replaceAll(",", "")' in script
    assert "const availableNumber =" in script
    assert "numeric > availableNumber" in script
    assert "availableNumber !== null" in script


def test_overdrawn_quantity_has_visible_review_warning():
    script = JS.read_text()

    assert "const overdrawnSupplies =" in script
    assert "supplies.filter(item => item.exceeds)" in script
    assert "if (overdrawnSupplies.length)" in script
    assert "only " in script
    assert "available)" in script


def test_navigation_focuses_excess_quantity():
    script = JS.read_text()

    assert (
        "...overdrawnSupplies.map(item => item.input)"
        in script
    )
    assert 'firstIssue.closest("details")' in script
    assert "firstIssue.focus({preventScroll:true})" in script


def test_new_review_does_not_submit_or_mutate_inventory():
    script = JS.read_text()

    for forbidden in (
        "fetch(",
        "requestSubmit(",
        "form.submit(",
        "localStorage.",
        "sessionStorage.",
    ):
        assert forbidden not in script

    assert "description.textContent = content" in script


def test_existing_backend_protections_and_template():
    html = HTML.read_text()

    assert "tracker-dose-final-review.js?v=20261103f" in html
    assert 'name="supply_qty_{{ s.id }}"' in html

    Environment().parse(html)

    backend = (
        ROOT / "app/routers/doses.py"
    ).read_text()

    assert "idempotency.check(" in backend
    assert "reserve_inventory_write" in backend
    assert "manual_supplies.deduct(" in backend
