"""Supplies stock health display regression tests."""

from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def test_stock_health_template():
    html = read("app/templates/supplies.html")

    assert "data-stock-health-summary" in html
    assert "tracker-stock-health.css" in html

    for value in (
        "Total Products",
        "Low Stock",
        "Out of Stock",
        "Available",
        "Review Purchases",
        'data-stock-state="low"',
        'data-stock-state="depleted"',
        'data-stock-state="available"',
    ):
        assert value in html


def test_threshold_logic():
    html = read("app/templates/supplies.html")

    assert (
        "item.remaining_qty * 4 <= item.purchased_qty"
        in html
    )
    assert (
        "s.remaining_qty * 4 <= s.purchased_qty"
        in html
    )
    assert "item.remaining_qty <= 0" in html
    assert "s.remaining_qty <= 0" in html


def test_usage_forms_unchanged():
    html = read("app/templates/supplies.html")

    assert 'name="submission_token"' in html
    assert 'data-tracker-supply-use' in html
    assert 'name="quantity"' in html
    assert 'data-remaining="{{ s.remaining_qty }}"' in html


def test_statuses_are_not_write_actions():
    html = read("app/templates/supplies.html")

    assert html.count(
        "data-stock-health-summary"
    ) == 1
    assert "tracker-stock-health.js" not in html


def test_template_parses():
    templates.env.get_template("supplies.html")
