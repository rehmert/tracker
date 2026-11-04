"""Correction supply picker prioritizes previously recorded usage."""

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment

from app.routers.doses import _correction_available_supplies

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "app/templates/dose_edit.html"
ROUTER = ROOT / "app/routers/doses.py"


def supply(sid, remaining, name="Supply", kind="syringe"):
    return SimpleNamespace(
        id=sid,
        remaining_qty=remaining,
        name=name,
        kind=kind,
    )


def test_original_usage_comes_before_new_supplies():
    supplied = [
        supply(1, 3),
        supply(2, 4),
        supply(3, 0),
        supply(4, 8),
    ]

    result = _correction_available_supplies(
        supplied, {3: 1, 2: 2}
    )

    assert [s.id for s in result] == [2, 3, 1, 4]
    assert [s.id for s in supplied] == [1, 2, 3, 4]


def test_no_original_usage_preserves_order():
    result = _correction_available_supplies(
        [supply(4, 2), supply(2, 0), supply(3, 1)],
        {},
    )
    assert [s.id for s in result] == [4, 3]


def test_zero_stock_original_supply_is_visible():
    result = _correction_available_supplies(
        [supply(1, 2), supply(2, 0)],
        {2: 3},
    )
    assert [s.id for s in result] == [2, 1]


def test_supplies_are_not_duplicated():
    result = _correction_available_supplies(
        [supply(1, 5), supply(2, 5)],
        {1: 1, 2: 2},
    )
    assert [s.id for s in result] == [1, 2]


def test_accessible_checkbox_identifies_supply():
    html = HTML.read_text()

    marker = (
        '<input aria-label="Use {{ s.name }} '
        'for corrected entry" type="checkbox" '
        'name="supply_id_used" value="{{ s.id }}"'
    )

    assert html.count(marker) == 1

    start = html.index(marker)
    end = html.index(">", start) + 1

    control = Environment(autoescape=True).from_string(
        html[start:end]
    )

    rendered = control.render(
        s=supply(
            31, 5,
            name="BD 1 mL Syringe",
        ),
        used={31: 2},
    )

    assert (
        'aria-label="Use BD 1 mL Syringe for corrected entry"'
        in rendered
    )
    assert 'value="31"' in rendered
    assert "checked" in rendered


def test_supply_name_is_html_escaped():
    html = HTML.read_text()

    marker = (
        '<input aria-label="Use {{ s.name }} '
        'for corrected entry"'
    )

    start = html.index(marker)
    end = html.index(">", start) + 1

    control = Environment(autoescape=True).from_string(
        html[start:end]
    )

    rendered = control.render(
        s=supply(4, 1, name='<script>alert(1)</script>'),
        used={},
    )

    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_existing_correction_contracts_remain():
    html = HTML.read_text()
    router = ROUTER.read_text()

    assert "Previously recorded supplies appear first." in html
    assert 'value="{{ used.get(s.id,1) }}"' in html
    assert "s.remaining_qty + used.get(s.id, 0)" in html
    assert 'class="dose-correction-original"' in html
    assert 'class="dose-audit-details"' in html

    post = router.split(
        '@router.post("/doses/{did}/edit")', 1
    )[1].split(
        '@router.get("/dose-workspace")', 1
    )[0]

    assert "reserve_inventory_write" in post
    assert "manual_supplies.selections(" in post
    assert "credits={u.supply_id:u.amount" in post
    assert 'action="edit"' in post
    assert "db.commit()" in post

    Environment().parse(html)
