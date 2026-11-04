"""Correction forms display total restorable supply availability."""

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/dose_edit.html"
ROUTER = ROOT / "app/routers/doses.py"


def stock_cell():
    html = TEMPLATE.read_text()
    marker = '<td class="dose-correction-available">'
    assert html.count(marker) == 1

    start = html.index(marker)
    end = html.index("</td>", start) + len("</td>")

    env = Environment(autoescape=True)
    env.filters["num"] = lambda value: f"{value:g}"

    return env.from_string(html[start:end])


def test_stock_header_and_total_formula():
    source = TEMPLATE.read_text()

    assert "<th>Available for correction</th>" in source
    assert "Available (plus original usage)" not in source

    assert (
        "s.remaining_qty + used.get(s.id, 0)"
        in source
    )

    Environment().parse(source)


def test_selected_supply_includes_original_credit():
    rendered = stock_cell().render(
        s=SimpleNamespace(id=10, remaining_qty=10),
        used={10: 2},
    )

    assert "12 available" in rendered
    assert "10 in stock" in rendered
    assert "2 originally used" in rendered


def test_unselected_supply_shows_current_stock():
    rendered = stock_cell().render(
        s=SimpleNamespace(id=11, remaining_qty=25),
        used={10: 2},
    )

    assert "25 available" in rendered
    assert "originally used" not in rendered


def test_fractional_supply_credit_is_preserved():
    rendered = stock_cell().render(
        s=SimpleNamespace(id=12, remaining_qty=4.5),
        used={12: 0.5},
    )

    assert "5 available" in rendered
    assert "4.5 in stock" in rendered
    assert "0.5 originally used" in rendered


def test_zero_stock_with_original_credit():
    rendered = stock_cell().render(
        s=SimpleNamespace(id=13, remaining_qty=0),
        used={13: 1},
    )

    assert "1 available" in rendered
    assert "0 in stock" in rendered


def test_edit_fields_and_audit_remain_intact():
    html = TEMPLATE.read_text()

    for marker in (
        'action="/doses/{{ dose.id }}/edit"',
        'name="supply_id_used"',
        'name="supply_qty_{{ s.id }}"',
        'data-counted="',
        'value="{{ used.get(s.id,1) }}"',
        'class="dose-audit-details"',
        'class="dose-audit-change-status"',
    ):
        assert marker in html


def test_backend_still_enforces_inventory():
    router = ROUTER.read_text()

    post = router.split(
        '@router.post("/doses/{did}/edit")', 1
    )[1].split(
        '@router.get("/dose-workspace")', 1
    )[0]

    assert "reserve_inventory_write" in post
    assert "manual_supplies.selections(" in post
    assert "credits={u.supply_id:u.amount" in post
    assert "db.commit()" in post
    assert 'action="edit"' in post
