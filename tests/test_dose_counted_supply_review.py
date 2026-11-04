"""Counted supplies must be reviewed using whole quantities."""

from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]

JS = ROOT / "app/static/js/tracker-dose-final-review.js"
HTML = ROOT / "app/templates/doses.html"
ROUTER = ROOT / "app/routers/doses.py"
BACKEND = ROOT / "app/manual_supplies.py"


def test_count_categories_come_from_database():
    source = ROUTER.read_text()

    assert "SupplyCategory" in source
    assert 'SupplyCategory.unit == "count"' in source
    assert "counted_supply_kinds=counted_supply_kinds" in source


def test_template_marks_counted_quantities():
    html = HTML.read_text()

    assert (
        "s.kind in counted_supply_kinds"
        in html
    )
    assert 'data-counted="' in html
    assert "tracker-dose-final-review.js?v=20261103f" in html

    Environment().parse(html)


def test_fractional_count_checked_only_for_count_categories():
    source = JS.read_text()

    assert 'input?.dataset.counted === "true"' in source
    assert "const fractionalCount = !invalid && counted &&" in source
    assert "!Number.isInteger(numeric)" in source
    assert "item.fractionalCount" in source
    assert '" (whole number required)"' in source


def test_issue_navigation_includes_fractional_counts():
    source = JS.read_text()

    assert (
        "...fractionalSupplies.map(item => item.input)"
        in source
    )
    assert "firstIssueButton.disabled = !firstIssue" in source
    assert "disclosure.open = true" in source


def test_server_keeps_final_validation():
    backend = BACKEND.read_text()

    assert 'cat.unit == "count"' in backend
    assert "not qty.is_integer()" in backend
    assert "Selected supplies exceed available stock." in backend

    router = ROUTER.read_text()
    assert "idempotency.check(" in router
    assert "reserve_inventory_write" in router
    assert "manual_supplies.deduct(" in router


def test_review_is_read_only():
    source = JS.read_text()

    for forbidden in (
        "fetch(",
        "requestSubmit(",
        "form.submit(",
        "localStorage.",
        "sessionStorage.",
    ):
        assert forbidden not in source
