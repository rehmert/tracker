"""Correction inventory summary counts affected supply types."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "app/static/js/tracker-dose-correction-review.js"
HTML = ROOT / "app/templates/dose_edit.html"
ROUTER = ROOT / "app/routers/doses.py"


def category(original, corrected):
    difference = original - corrected
    if difference > 0:
        return "returned"
    if difference < 0:
        return "consumed"
    return "unchanged"


def test_partial_reversal_returns_stock():
    assert category(2, 1) == "returned"


def test_deselection_returns_stock():
    assert category(1, 0) == "returned"


def test_new_supply_consumes_stock():
    assert category(0, 2) == "consumed"


def test_larger_corrected_usage_consumes_stock():
    assert category(1, 3) == "consumed"


def test_unchanged_usage_is_neutral():
    assert category(1, 1) == "unchanged"


def test_fractional_usage():
    assert category(0.5, 0.25) == "returned"
    assert category(0.5, 0.75) == "consumed"


def test_javascript_counts_supply_types():
    source = JS.read_text()

    markers = (
        "const movementCounts = {",
        "returned: 0,",
        "consumed: 0,",
        "unchanged: 0",
        "movementCounts.returned += 1;",
        "movementCounts.consumed += 1;",
        "movementCounts.unchanged += 1;",
        '" supply types returning stock · "',
        '" consuming stock · "',
        '" unchanged."',
    )

    for marker in markers:
        assert marker in source, marker


def test_summary_is_only_shown_when_valid():
    source = JS.read_text()

    assert "if (!issues.length)" in source
    assert "if (!issues.length && projections.length)" in source
    assert "panel.insertBefore(movementSummary, heading);" in source

    # Counts are per supply type, never across mixed units.
    assert "movementCounts.returned += 1;" in source
    assert "movementCounts.consumed += 1;" in source


def test_preview_remains_advisory():
    source = JS.read_text()

    assert "item.textContent = projection;" in source
    assert "movementSummary.textContent =" in source
    assert "qty > available + 1e-9" in source
    assert "Number.isInteger(qty)" in source

    for forbidden in (
        "fetch(",
        "requestSubmit(",
        "form.submit(",
        "localStorage.",
        "sessionStorage.",
    ):
        assert forbidden not in source


def test_template_and_backend_stay_compatible():
    html = HTML.read_text()
    router = ROUTER.read_text()

    assert "?v=20261104g" in html
    assert 'id="tracker-dose-correction-review"' in html
    assert 'data-original="{{ used.get(s.id, 0) }}"' in html

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
