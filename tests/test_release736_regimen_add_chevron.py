"""Release 736 disclosure regression, updated for Release 737's intentionally
changed design: the Add controls now match Quick Log's native LEFT marker.
Retain all viewport and light/dark combinations from the original test.
"""
from pathlib import Path
import re

import pytest
from jinja2 import Environment
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/regimen635.html"
APP_CSS = ROOT / "app/static/app.css"
LABELS = (
    "Log a supplement or medication independently",
    "Add supplement or medication", "Add schedule",
)


def markup():
    source = TEMPLATE.read_text(encoding="utf-8")
    Environment().parse(source)
    css = source.split("<style>", 1)[1].split("</style>", 1)[0]
    assert "summary.reg737-native-disclosure{" in css
    assert "summary.reg733-add-trigger::after" not in css
    summaries = []
    for label in LABELS:
        match = re.search(
            r'<summary class="reg737-native-disclosure"><strong>'
            + re.escape(label) + r"</strong></summary>", source
        )
        assert match is not None, label
        summaries.append(match.group(0))
    return (
        '<!doctype html><html><head>'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<style>" + APP_CSS.read_text(encoding="utf-8") + "</style>"
        "<style>" + css + "</style>"
        '</head><body><main id="main-content">'
        + "".join(
            '<section class="card"><details id="disclosure-' + str(idx) + '">'
            + summary + '<div><input aria-label="Test value" value="Example"/></div>'
            + "</details></section>"
            for idx, summary in enumerate(summaries)
        ) + "</main></body></html>"
    )


def test_736_template_add_disclosures_still_use_semantic_native_details():
    html = markup()
    for label in LABELS:
        assert label in html
    assert "data-reg733-edit" not in html
    assert html.count('<summary class="reg737-native-disclosure">') == 3


@pytest.mark.parametrize("width", [320, 390, 760, 1024])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_736_chevron_is_visible_rotates_and_expands_at_mobile_desktop_sizes(
    width, scheme,
):
    html = markup()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": width, "height": 844},
                color_scheme=scheme,
            )
            page.set_content(html)
            baseline = None
            for idx, label in enumerate(LABELS):
                details = page.locator(f"#disclosure-{idx}")
                summary = details.locator("summary")
                expect(summary).to_have_text(label)
                expect(details).not_to_have_attribute("open", "")
                closed = summary.evaluate(
                    """el => {
                        const s = getComputedStyle(el);
                        return {
                            display: s.display,
                            listType: s.listStyleType,
                            after: getComputedStyle(el, '::after').content,
                            marker: getComputedStyle(el, '::marker').content,
                            height: el.getBoundingClientRect().height,
                            textOffset: el.querySelector('strong').getClientRects()[0].left
                                - el.getBoundingClientRect().left
                        };
                    }"""
                )
                assert closed["display"] == "list-item", closed
                assert closed["listType"] == "disclosure-closed", closed
                assert closed["after"] == "none", closed
                assert closed["height"] >= 44, (width, scheme, label)
                if baseline is None:
                    baseline = closed
                else:
                    assert {k: v for k, v in closed.items() if k != 'height'} == {k: v for k, v in baseline.items() if k != 'height'}, (width, scheme, label, closed, baseline)
                summary.click()
                expect(details).to_have_attribute("open", "")
                assert summary.evaluate(
                    "el => getComputedStyle(el).listStyleType"
                ) == "disclosure-open", (width, scheme, label)
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                ), (width, scheme)
                summary.click()
                expect(details).not_to_have_attribute("open", "")
        finally:
            browser.close()
