"""Release 603: inventory/purchase mobile navigation and form safety.

All new controls preserve canonical rows, native POST fields and explicit
user-triggered writes. No backend, database or migration changes.
"""
from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_603_purchase_list_form_and_filters_are_preserved():
    html = source("app/templates/purchases.html")
    for marker in (
        'id="purchase-history-table"',
        "data-purchase-row",
        "data-purchase-total-cents",
        "data-purchase-search",
        "data-purchase-vendor",
        "data-purchase-status",
        "data-purchase-from",
        "data-purchase-through",
        "data-purchase-reset",
        "data-purchase-export",
        "tracker-purchase-history-review.js?v=603",
        "tracker-purchase-mobile603.js?v=603",
        "tracker-inventory-mobile603.css?v=603",
        'class="purchase-review-more603"',
        "data-purchase-date-active603",
        'id="new-purchase"',
        'form method="post" action="/purchases"',
        'name="submission_token"',
    ):
        assert marker in html, marker
    assert html.count('form method="post" action="/purchases"') == 1
    assert html.count('data-purchase-row') == 1
    assert html.count('data-mobile-optional603') == 2
    assert "Needs items · Add inventory" in html
    assert 'data-purchase-visible-total' in html
    for field in ("vendor", "purchased_on", "order_ref",
                  "shipping", "tax", "discount", "notes"):
        assert 'name="' + field + '"' in html
    templates.env.get_template("purchases.html")


def test_603_detail_retains_original_vial_pricing_and_counters():
    html = source("app/templates/purchase_detail.html")
    for marker in (
        'id="purchase-vial-form"',
        "tracker-purchase-vials.js?v=20261101",
        "tracker-purchase-mobile603.js?v=603",
        "tracker-inventory-mobile603.css?v=603",
        'id="purchase-vial-price-amount"',
        'id="purchase-vial-preview"',
        'id="purchase-vial-submit"',
        'id="purchase-vial-kits-field"',
        'name="submission_token"',
        'name="kit_count"',
        'name="kit_size"',
        'name="quantity"',
        'name="price_basis"',
        'name="unit_price"',
        'name="volume_ml"',
        'name="concentration"',
        'name="content_value"',
        'name="content_unit"',
        'name="cap_color"',
        'name="label"',
        'name="lot"',
        'name="expires_on"',
        'name="notes"',
        "data-mobile-optional603",
        "purchase-optional-grid603",
    ):
        assert marker in html, marker
    assert html.count('name="cap_color"') == 1
    assert html.count('id="purchase-vial-form"') == 1
    assert "disabled" not in html.split("purchase-optional-grid603", 1)[1].split(
        "</details>", 1
    )[0]
    templates.env.get_template("purchase_detail.html")


def test_603_mobile_purchase_cards_do_not_clone_rows_or_write_data():
    js = source("app/static/js/tracker-purchase-mobile603.js")
    for marker in (
        "document.querySelector('[data-purchase-history]')",
        "table.closest('.scroll')",
        "tbody tr[data-purchase-row]",
        "row.cells.length !== labels.length",
        "cell.dataset.purchaseLabel603",
        "tracker-purchase-cards603",
        "tracker-purchase-card-wrap603",
        "window.matchMedia('(max-width: 760px)')",
        "details.open = false",
        "details.open = true",
        "data-purchase-date-active603",
        "updateDateMarker",
        "aria-controls",
        "aria-pressed",
        "localStorage.getItem(KEY)",
    ):
        assert marker in js, marker
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "requestSubmit(",
        ".submit(",
        "FormData(",
        "cloneNode",
        "document.createElement('tr')",
        ".value =",
    ):
        assert forbidden not in js, forbidden
    assert js.count("document.createElement('button')") == 1
    assert "save" not in js.lower().split("function render()", 1)[-1]


def test_603_purchase_filter_index_preserves_sort_and_exports():
    js = source("app/static/js/tracker-purchase-history-review.js")
    for marker in (
        "const searchableByRow = new Map(rows.map(row => [",
        "const searchable = searchableByRow.get(row)",
        "function compare(a, b)",
        "function updateSortState()",
        "function exportCsv()",
        "visibleRows()",
        "from.value > through.value",
        "row.hidden = !match",
        "exportButton.disabled = shown === 0",
        "sumCents += cents(row)",
        "tracker-purchase-history-filtered.csv",
    ):
        assert marker in js, marker
    assert "fetch(" not in js
    assert "localStorage" not in js
    assert "sessionStorage" not in js


def test_603_vials_retain_all_bulk_tools_and_jump_open_sections():
    html = source("app/templates/vials.html")
    js = source("app/static/js/tracker-vial-jumps603.js")
    for marker in (
        "tracker-vial-jumps603",
        "tracker-vial-jumps603.js?v=603",
        "tracker-inventory-mobile603.css?v=603",
        'href="#tracker-vials-sortable"',
        'href="#tracker-vial-find-panel"',
        'href="#bulk-selection-toolbar"',
        'href="#tracker-inventory-reports"',
        'href="#tracker-vial-lifecycle"',
        'href="/purchases#new-purchase"',
        'id="tracker-vials-sortable"',
        'id="bulk-selection-toolbar"',
        'id="bulk-select-all"',
        'id="bulk-select-none"',
        'id="bulk-undo-selection"',
        'id="bulk-open-editor"',
        'id="bulk-delete-selected"',
        'id="bulk-vials"',
        'id="bulk-editor-panel"',
    ):
        assert marker in html, marker
    assert "document.getElementById(id)" in js
    assert "element.tagName === 'DETAILS'" in js
    assert "element.open = true" in js
    assert "fetch(" not in js
    assert "requestSubmit(" not in js
    templates.env.get_template("vials.html")


def test_603_quick_entry_daily_is_opt_in_and_preserves_actions():
    html = source("app/templates/quick_entry.html")
    js = source("app/static/js/tracker-quick-entry.js")
    assert html.count("tracker-quick-entry.js?v=603") == 1
    assert html.count('data-quick-category="all"') == 1
    assert html.count('data-quick-category="daily"') == 1
    assert html.count("data-quick-daily") == 5
    assert 'data-quick-category="record"' in html
    assert 'data-quick-category="review"' in html
    for marker in (
        "category = 'all'",
        "const searchableByAction = new Map",
        "category === 'daily'",
        "action.hasAttribute('data-quick-daily')",
        "const searchable = searchableByAction.get(action)",
        "action.hidden = !show",
        "visible[next].focus()",
        "window.location.assign",
        "search.focus()",
    ):
        assert marker in js, marker
    for forbidden in ("fetch(", "requestSubmit(", ".submit("):
        assert forbidden not in js
    templates.env.get_template("quick_entry.html")


def test_603_mobile_styles_and_browser_matrix():
    css = source("app/static/css/tracker-inventory-mobile603.css")
    browser = source("tests/browser/test_strict_csrf521.py")
    for marker in (
        "@media screen and (max-width: 760px)",
        "@media screen and (max-width: 359px)",
        "tracker-purchase-mobile-controls603",
        "tracker-purchase-cards603",
        "tracker-purchase-card-wrap603",
        ".purchase-optional603",
        ".purchase-review-more603",
        ".purchase-review-advanced-grid603",
        ".tracker-vial-jumps603",
        "#bulk-selection-toolbar",
        "overflow: visible",
        "scroll-margin-top",
        "min-height: 44px",
        ":focus-visible",
    ):
        assert marker in css, marker
    assert css.count("{") == css.count("}")
    for name in (
        "test_603_purchase_phone_cards_dates_and_native_order_fields",
        "test_603_vials_navigation_and_daily_action_filter",
    ):
        assert browser.count("def " + name + "(") == 1
        preceding = browser.split("def " + name + "(", 1)[0]
        assert '@pytest.mark.parametrize("scheme", ("http", "https"))' in preceding[-100:]
    assert 'new FormData(form)' in browser
    assert 'a[data-quick-action]:not([hidden])' in browser
    assert "controls.get_by_role" in browser


def test_603_mobile_dock_pointer_focus_safety():
    shell = source("app/static/js/tracker-mobile-shell507.js")
    base = source("app/templates/base.html")
    browser = source("tests/test_mobile_dock_pointer603.py")
    for marker in (
        "let pointerInFlight = false",
        'document.addEventListener("pointerdown"',
        'document.addEventListener("pointerup", finishPointer, true)',
        'document.addEventListener("pointercancel", finishPointer, true)',
        "if (pointerInFlight && !isEditingField(document.activeElement)) return",
        "if (!pointerInFlight) refreshKeyboardState()",
        "requestAnimationFrame",
    ):
        assert marker in shell, marker
    assert "tracker-mobile-shell507.js?v=603" in base
    assert "tracker-mobile-shell507.js?v=507" not in base
    for marker in ("[320, 390, 430]", "toggle.click()", "data-purchase-reset",
                   'getComputedStyle(document.querySelector'):
        assert marker in browser, marker
    assert "force=True" not in browser
