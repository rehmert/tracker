"""Dose corrections show stocked supplies and original usage."""

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment

from app.routers.doses import _correction_available_supplies

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "app/templates/dose_edit.html"
ROUTER = ROOT / "app/routers/doses.py"


def item(sid, qty):
    return SimpleNamespace(id=sid, remaining_qty=qty)


def test_currently_stocked_supplies_remain_visible():
    result = _correction_available_supplies(
        [item(1, 5), item(2, 0), item(3, 0.5)],
        {},
    )
    assert [s.id for s in result] == [1, 3]


def test_originally_used_zero_stock_supply_remains_visible():
    result = _correction_available_supplies(
        [item(1, 0), item(2, 0), item(3, 4)],
        {1: 2},
    )
    assert [s.id for s in result] == [1, 3]


def test_existing_order_and_no_duplicates():
    result = _correction_available_supplies(
        [item(3, 1), item(1, 0), item(2, 5)],
        {3: 1, 1: 1},
    )
    assert [s.id for s in result] == [3, 1, 2]


def test_original_usage_and_audit_names_are_retained():
    router = ROUTER.read_text()

    start = router.index(
        '@router.get("/doses/{did}/edit")'
    )
    end = router.index(
        '@router.post("/doses/{did}/edit")',
        start,
    )
    edit = router[start:end]

    assert "used = {" in edit
    assert "all_supplies = list(db.scalars(" in edit
    assert (
        "str(s.id): s.name for s in all_supplies"
        in edit
    )
    assert "_correction_available_supplies(" in edit
    assert "supplies=supplies, used=used" in edit
    assert "supply_names=supply_names" in edit


def test_edit_form_preserves_usage_and_audit():
    html = HTML.read_text()

    assert (
        "Only supplies currently in stock or "
        "originally used by this dose are listed."
        in html
    )
    assert 'name="supply_id_used"' in html
    assert 'value="{{ used.get(s.id,1) }}"' in html
    assert "s.remaining_qty + used.get(s.id, 0)" in html
    assert 'class="dose-audit-details"' in html

    Environment().parse(html)


def test_correction_post_remains_unchanged():
    router = ROUTER.read_text()

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
