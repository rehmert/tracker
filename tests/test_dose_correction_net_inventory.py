"""Net inventory preview: returns, consumption and unchanged usage."""

from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "app/static/js/tracker-dose-correction-review.js"
HTML = ROOT / "app/templates/dose_edit.html"
ROUTER = ROOT / "app/routers/doses.py"


def movement(current, original, corrected):
    """Independent arithmetic reference for correction scenarios."""
    available = current + original
    remaining = available - corrected
    delta = original - corrected
    return remaining, delta


def test_partial_reversal_returns_inventory():
    assert movement(10, 2, 1) == (11, 1)


def test_deselection_returns_all_original_usage():
    assert movement(0, 1, 0) == (1, 1)


def test_new_supply_consumes_inventory():
    assert movement(25, 0, 2) == (23, -2)


def test_unchanged_usage_has_zero_net_effect():
    assert movement(6, 1, 1) == (6, 0)


def test_fractional_correction():
    remaining, delta = movement(4.5, 0.5, 0.25)
    assert remaining == 4.75
    assert delta == 0.25


def test_javascript_uses_correct_net_arithmetic():
    js = JS.read_text()

    markers = (
        "const remaining = available - corrected;",
        "const delta = original - corrected;",
        "const current = available - original;",
        'display(delta) + " returned"',
        'display(-delta) + " consumed"',
        ': "unchanged";',
        '" from " + display(current) + " current stock"',
    )

    for marker in markers:
        assert marker in js, marker


def test_preview_is_suppressed_on_invalid_quantities():
    js = JS.read_text()

    assert "if (!issues.length)" in js
    assert "if (!issues.length && projections.length)" in js
    assert "qty > available + 1e-9" in js
    assert "Number.isInteger(qty)" in js


def test_read_only_rendering():
    js = JS.read_text()

    assert "item.textContent = projection;" in js

    for forbidden in (
        "fetch(",
        "requestSubmit(",
        "form.submit(",
        "localStorage.",
        "sessionStorage.",
    ):
        assert forbidden not in js


def test_template_and_backend_contracts():
    html = HTML.read_text()
    router = ROUTER.read_text()

    assert "?v=20261104f" in html
    assert 'id="tracker-dose-correction-review"' in html
    assert 'data-original="{{ used.get(s.id, 0) }}"' in html
    assert 'name="supply_id_used"' in html

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
