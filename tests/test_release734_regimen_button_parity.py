"""Release 734: matching native Edit summary and Delete/Archive/Stop buttons."""
from pathlib import Path
import re

import pytest
from jinja2 import Environment
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/regimen635.html"
APP_CSS = ROOT / "app/static/app.css"

FIELDS = (
    "display", "boxSizing", "minHeight", "paddingTop", "paddingRight",
    "paddingBottom", "paddingLeft", "borderTopWidth", "borderTopStyle",
    "borderTopColor", "borderRadius", "backgroundColor", "color",
    "fontFamily", "fontSize", "fontWeight", "lineHeight",
    "textAlign", "cursor", "appearance",
)


def test_734_real_template_uses_one_shared_macd_button_style():
    source = TEMPLATE.read_text(encoding="utf-8")
    Environment().parse(source)
    assert re.search(
        r'<summary class="reg733-edit-trigger reg734-macd-action" '
        r'data-reg733-edit>Edit \{\{ item\.kind \}\}</summary>', source
    )
    assert re.search(
        r'<summary class="reg733-edit-trigger reg734-macd-action" '
        r'data-reg733-edit>Edit schedule</summary>', source
    )
    assert 'class="reg734-macd-action" name="confirm_delete" value="delete"' in source
    assert '<button type="submit" class="reg734-macd-action">Archive</button>' in source
    assert '<button type="submit" class="reg734-macd-action">Stop schedule</button>' in source
    assert ".reg733-edit-trigger::after{content:" not in source
    assert 'summary.reg734-macd-action::after{content:none}' in source
    assert "data-reg732-delete" in source  # Original delete confirmation unchanged.


@pytest.mark.parametrize("width", (320, 390, 760, 1024))
@pytest.mark.parametrize("scheme", ("light", "dark"))
def test_734_edit_and_delete_computed_styles_match_and_still_work(width, scheme):
    source = TEMPLATE.read_text(encoding="utf-8")
    inline_style = source.split("<style>", 1)[1].split("</style>", 1)[0]
    app_css = APP_CSS.read_text(encoding="utf-8")
    # The HTML elements and class names below mirror the real native
    # disclosure and POST controls. This tests *computed* browser styles,
    # not merely the presence of class strings.
    html = (
        '<!doctype html><html><head>'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>' + app_css + '</style><style>' + inline_style + '</style>'
        '</head><body><main id="main-content">'
        '<article class="reg635-card">'
        '<div class="reg635-actions ux673-action-row reg733-action-row">'
        '<details class="reg733-edit-panel">'
        '<summary class="reg733-edit-trigger reg734-macd-action" '
        'data-reg733-edit>Edit medication</summary>'
        '<form method="post" action="/regimen/items/1/edit" class="reg635-form">'
        '<input name="name" value="Example medication">'
        '<button type="submit">Save item</button></form></details>'
        '<form action="/regimen/items/1/archive" method="post">'
        '<button type="submit" class="reg734-macd-action">Archive</button></form>'
        '<form action="/regimen/items/1/delete" method="post" '
        'onsubmit="return confirm(&quot;Delete medication?&quot;)">'
        '<button type="submit" class="reg734-macd-action" '
        'name="confirm_delete" value="delete">Delete medication</button></form>'
        '</div></article></main></body></html>'
    )
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": width, "height": 844},
                color_scheme=scheme,
            )
            page.set_content(html)
            edit = page.locator("summary[data-reg733-edit]")
            delete = page.get_by_role("button", name="Delete medication")
            archive = page.get_by_role("button", name="Archive")

            def styles(locator):
                return locator.evaluate(
                    "(el, fields) => {const s = getComputedStyle(el);"
                    "return Object.fromEntries(fields.map(f => [f, s[f]]));}",
                    list(FIELDS),
                )

            edit_style = styles(edit)
            assert edit_style == styles(delete), (width, scheme, "delete", edit_style, styles(delete))
            assert edit_style == styles(archive), (width, scheme, "archive")
            assert edit.evaluate(
                "el => getComputedStyle(el, '::after').content"
            ) == "none"
            for button in (edit, delete, archive):
                assert button.evaluate(
                    "el => el.getBoundingClientRect().height >= 44"
                ), (width, scheme, button.text_content())

            form = page.locator('form[action="/regimen/items/1/edit"]')
            expect(form).to_be_hidden()
            edit.click()
            expect(form).to_be_visible()
            expect(form.locator('[name="name"]')).to_have_value("Example medication")
            edit.click()
            expect(form).to_be_hidden()
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            ), (width, scheme)
        finally:
            browser.close()
