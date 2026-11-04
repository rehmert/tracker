"""Review estimated inventory following dose correction."""

from pathlib import Path
from types import SimpleNamespace
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "app/templates/dose_edit.html"
JS = ROOT / "app/static/js/tracker-dose-correction-review.js"
ROUTER = ROOT / "app/routers/doses.py"


def quantity_input():
    source = HTML.read_text()
    marker = 'name="supply_qty_{{ s.id }}"'
    assert source.count(marker) == 1
    position = source.index(marker)
    start = source.rfind("<input", 0, position)
    end = source.index(">", position) + 1

    return Environment(autoescape=True).from_string(
        source[start:end]
    )


def render_input(stock, original):
    return quantity_input().render(
        s=SimpleNamespace(
            id=4,
            name="Syringe",
            kind="syringe",
            remaining_qty=stock,
        ),
        used={4: original} if original else {},
        counted_supply_kinds={"syringe"},
    )


def test_original_stock_credit_metadata():
    rendered = render_input(10, 2)
    assert 'data-original="2"' in rendered
    assert 'data-available="12"' in rendered
    assert 'value="2"' in rendered


def test_unselected_supply_metadata():
    rendered = render_input(25, 0)
    assert 'data-original="0"' in rendered
    assert 'data-available="25"' in rendered


def test_minimal_supply_fixture_still_renders():
    rendered = quantity_input().render(
        s=SimpleNamespace(
            id=4, name="Syringe", kind="syringe"
        ),
        used={4: 2},
        counted_supply_kinds={"syringe"},
    )
    assert 'data-available="2"' in rendered
    assert 'data-original="2"' in rendered


def test_preview_accounts_for_deselection():
    js = JS.read_text()

    assert "const allChecks = form.querySelectorAll(" in js
    assert 'input[name="supply_id_used"]' in js
    assert "input?.dataset.original" in js
    assert "input?.dataset.available" in js
    assert "checkbox.checked" in js
    assert "if (!checkbox.checked && original <= 0) continue;" in js
    assert "const remaining = available - corrected;" in js
    assert "if (!issues.length && projections.length)" in js


def test_preview_is_read_only_and_escapes_names():
    js = JS.read_text()

    assert "item.textContent = projection;" in js
    assert "panel.append(heading, list);" in js
    assert "number.toFixed(6)" in js

    for forbidden in (
        "fetch(",
        "requestSubmit(",
        "form.submit(",
        "localStorage.",
        "sessionStorage.",
    ):
        assert forbidden not in js


def test_previous_review_and_inventory_validation_remain():
    source = HTML.read_text()
    router = ROUTER.read_text()
    js = JS.read_text()

    assert "?v=20261104d" in source
    assert 'id="tracker-dose-correction-review"' in source
    assert "qty > available + 1e-9" in js
    assert "Number.isInteger(qty)" in js

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

    Environment().parse(source)
