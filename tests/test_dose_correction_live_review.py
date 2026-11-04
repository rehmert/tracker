"""Live disposable correction review remains advisory and read-only."""

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

    location = source.index(marker)
    start = source.rfind("<input", 0, location)
    end = source.index(">", location) + 1

    return Environment(autoescape=True).from_string(
        source[start:end]
    )


def test_review_panel_and_script_are_loaded():
    html = HTML.read_text()

    assert 'id="tracker-dose-correction-form"' in html
    assert 'id="tracker-dose-correction-review"' in html
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html

    assert (
        "/static/js/tracker-dose-correction-review.js"
        "?v=20261104d"
        in html
    )

    Environment().parse(html)


def test_correctable_stock_includes_original_usage():
    rendered = quantity_input().render(
        s=SimpleNamespace(
            id=10,
            name="Syringe",
            kind="syringe",
            remaining_qty=4,
        ),
        used={10: 2},
        counted_supply_kinds={"syringe"},
    )

    assert 'data-available="6"' in rendered
    assert 'data-counted="true"' in rendered
    assert 'value="2"' in rendered


def test_fractional_supply_is_supported():
    rendered = quantity_input().render(
        s=SimpleNamespace(
            id=11,
            name="BAC water",
            kind="bac_water",
            remaining_qty=4.5,
        ),
        used={11: 0.5},
        counted_supply_kinds={"syringe"},
    )

    assert 'data-available="5.0"' in rendered
    assert 'data-counted="false"' in rendered
    assert 'value="0.5"' in rendered


def test_existing_minimal_fixture_still_renders():
    rendered = quantity_input().render(
        s=SimpleNamespace(
            id=10,
            name="Needle",
            kind="needle",
        ),
        used={10: 2},
        counted_supply_kinds={"needle"},
    )

    assert 'data-available="2"' in rendered
    assert 'data-counted="true"' in rendered
    assert 'value="2"' in rendered


def test_review_only_checks_selected_supplies():
    js = JS.read_text()

    assert (
        'input[name="supply_id_used"]:checked'
        in js
    )
    assert "Number.isFinite(qty)" in js
    assert "Number.isInteger(qty)" in js
    assert "input?.dataset.counted" in js
    assert "input?.dataset.available" in js
    assert "qty > available + 1e-9" in js


def test_review_is_live_and_escapes_supply_names():
    js = JS.read_text()

    assert 'form.addEventListener("input", render)' in js
    assert 'form.addEventListener("change", render)' in js
    assert "entry.textContent = issue" in js
    assert "panel.replaceChildren()" in js

    for forbidden in (
        "fetch(",
        "requestSubmit(",
        "form.submit(",
        "localStorage.",
        "sessionStorage.",
    ):
        assert forbidden not in js


def test_correction_backend_protections_remain():
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
