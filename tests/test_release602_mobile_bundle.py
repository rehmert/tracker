"""Release 602 consolidated daily UX source contracts.

All enhancements are read-only; the original dose, food and vitals
backend workflows and CSRF/idempotency protections remain authoritative.
"""
from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app/templates"
SCRIPTS = ROOT / "app/static/js"
STYLES = ROOT / "app/static/css"
BROWSER = ROOT / "tests/browser/test_strict_csrf521.py"


def source(path):
    return (ROOT / path).read_text()


def test_602_dose_draft_fastpath_and_original_form():
    html = source("app/templates/doses.html")
    for marker in (
        "tracker-dose-fast602",
        "tracker-dose-progress602",
        "tracker-dose-history602.js?v=602",
        "tracker-dose-fast602.js?v=602",
        "tracker-mobile-daily602.css?v=602",
        'id="tracker-dose-amount602"',
        'id="tracker-dose-when602"',
        'id="tracker-dose-final-review"',
        'id="tracker-dose-submit-373"',
        'href="/doses?repeat_from={{ r.dose.id }}#quick-dose-entry"',
    ):
        assert marker in html, marker

    for marker in (
        'form class="grid" hx-post="/doses"',
        'name="submission_token"',
        'name="vial_id"',
        'name="amount"',
        'name="taken_at"',
        'hx-post="/doses/preview"',
        'hx-target="#dose-preview"',
        'hx-target="#dose-body"',
        'id="dose-body"',
    ):
        assert marker in html, marker
    assert html.index('data-dose-fast602') < html.index('form class="grid"')
    assert html.count('hx-post="/doses"') == 1
    assert html.count("tracker-dose-final-review.js") == 1
    templates.env.get_template("doses.html")


def test_602_mobile_guidance_has_no_write_or_prefill_actions():
    js = source("app/static/js/tracker-dose-fast602.js")
    for marker in (
        "form.elements.namedItem",
        "Number.isFinite(numeric)",
        "value('taken_at')",
        "field('use_remaining')",
        "steps.review.dataset.complete602 = 'false'",
        "form.addEventListener('input'",
        "form.addEventListener('change'",
        "tracker:dose-saved",
        "requestAnimationFrame(update)",
    ):
        assert marker in js, marker
    for disallowed in (
        "fetch(",
        ".submit(",
        "requestSubmit(",
        "form.action",
        "localStorage",
        "sessionStorage",
        "FormData(",
        ".value =",
    ):
        assert disallowed not in js, disallowed


def test_602_history_preserves_htmx_and_dose_rows():
    js = source("app/static/js/tracker-dose-history602.js")
    dose = source("app/templates/_dose_rows.html")
    assert "document.getElementById('dose-body')" in js
    assert "row.cells.length !== 8" in js
    assert "htmx:afterSwap" in js
    assert "tracker:dose-saved" in js
    assert "aria-expanded" in js
    assert "row.dataset.expanded602" in js
    assert "cloneNode" not in js
    assert "fetch(" not in js
    assert "form.submit(" not in js
    assert 'hx-delete="/doses/{{ r.dose.id }}"' in dose
    assert '/doses?repeat_from={{ r.dose.id }}' in dose


def test_602_food_mobile_and_filter_index_stable():
    html = source("app/templates/food.html")
    mobile = source("app/static/js/tracker-food-mobile602.js")
    filtered = source("app/static/js/tracker-food500.js")
    accordion = source("app/static/js/tracker-food382.js")
    assert html.count("tracker-food500.js?v=602") == 1
    assert html.count("tracker-food382.js?v=602") == 1
    assert html.count("tracker-food-mobile602.js?v=602") == 1
    assert html.count("tracker-mobile-daily602.css?v=602") == 1
    assert 'food424-actions food-mobile-actions602' in html
    assert "quick.open = true" in mobile
    assert "query.has('q')" in mobile
    assert "location.hash" in mobile
    assert "fetch(" not in mobile
    assert "requestSubmit(" not in mobile
    assert "const entries = cards.map(card =>" in filtered
    assert "for (const {card, searchable} of entries)" in filtered
    assert "requestAnimationFrame" in filtered
    assert "card.hidden = !visible" in filtered
    assert "section.open = true" in accordion
    assert "prefers-reduced-motion: reduce" in accordion
    assert "decodeURIComponent" in accordion
    assert "catch (_)" in accordion
    assert 'action="/food/quick/{{ item.id }}"' in html
    assert 'id="food-quick-log"' in html
    templates.env.get_template("food.html")


def test_602_mobile_density_and_existing_quick_navigation():
    css = source("app/static/css/tracker-mobile-daily602.css")
    quick = source("app/templates/quick_entry.html")
    for marker in (
        "max-width: 760px",
        "min-width: 360px",
        "min-width: 380px",
        "max-width: 359px",
        ".tracker-dose-steps602",
        ".tracker-dose-recent-links602",
        ".tracker-dose-history-toggle602",
        "data-dose-history602",
        ".food423-macros",
        ".food425-water-presets",
        ".tracker-quick-entry-grid",
        ":focus-visible",
        "min-height: 44px",
    ):
        assert marker in css, marker
    assert css.count("{") == css.count("}")
    assert "scroll-padding-bottom: calc(5.4rem" in css
    assert "scroll-margin-bottom: calc(5.4rem" in css
    assert "#main-content #dose-history .scroll {" in css
    assert "#main-content #dose-history {" in css
    assert "padding-bottom: calc(8rem + env(safe-area-inset-bottom, 0px));" in css
    assert "overflow: visible;" in css
    assert quick.count("tracker-mobile-daily602.css?v=602") == 1
    assert 'data-quick-search' in quick
    assert 'data-quick-action' in quick
    assert 'href="/doses#quick-dose-entry"' in quick
    templates.env.get_template("quick_entry.html")


def test_602_no_backend_mutations_and_browser_matrix():
    backend = source("app/routers/doses.py")
    for marker in (
        "idempotency.check(",
        "reserve_inventory_write",
        "require_inventory_write",
    ):
        assert marker in backend
    test = BROWSER.read_text()
    for name in (
        "test_602_mobile_dose_guidance_and_history_are_read_only",
        "test_602_food_and_quick_entry_phone_density",
    ):
        assert test.count("def " + name + "(") == 1
        preceding = test.split("def " + name + "(", 1)[0]
        assert '@pytest.mark.parametrize("scheme", ("http", "https"))' in preceding[-110:]
    assert "320" in test
    assert "390" in test
    assert "tracker-dose-fast602" in test
    assert "tracker-dose-history602" in test
    assert "document.elementFromPoint(x, y)" in test
    assert 'overflow == {"x": "visible", "y": "visible"}' in test
    assert "toggle.click(force=True)" not in test


def test_602_notes_user_titles_are_not_reformatted():
    template = source("app/templates/page_view.html")
    browser = BROWSER.read_text()
    assert '<h1 data-no-title-case>{{ p.title }}</h1>' in template
    assert 'expect(heading).to_have_text(updated)' in browser
    assert "to_have_value(updated)" in browser
    templates.env.get_template("page_view.html")
