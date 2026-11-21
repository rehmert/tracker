"""Release 737: shared native left-side arrowheads, not custom right chevrons."""
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
    "Add supplement or medication",
    "Add schedule",
)


def test_737_real_template_stays_native_and_consistent():
    source = TEMPLATE.read_text(encoding="utf-8")
    Environment().parse(source)
    css = source.split("<style>", 1)[1].split("</style>", 1)[0]
    assert "summary.reg737-native-disclosure{" in css
    assert "display:list-item" in css
    assert "min-height:44px" in css
    assert "reg733-add-trigger" not in source
    for label in LABELS:
        assert re.search(
            r'<summary class="reg737-native-disclosure"><strong>'
            + re.escape(label) + r"</strong></summary>", source
        ), label


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_737_native_marker_left_and_keyboard_toggle_matches_quick_log(scheme):
    source = TEMPLATE.read_text(encoding="utf-8")
    css = source.split("<style>", 1)[1].split("</style>", 1)[0]
    summaries = [
        re.search(
            r'<summary class="reg737-native-disclosure"><strong>'
            + re.escape(label) + r"</strong></summary>", source
        ).group(0) for label in LABELS
    ]
    html = (
        '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>' + APP_CSS.read_text(encoding="utf-8") + '</style>'
        '<style>' + css + '</style></head><body><main id="main-content">'
        + ''.join(
            '<section class="card"><details id="test-' + str(i) + '">'
            + summary + '<p>Expanded content</p></details></section>'
            for i, summary in enumerate(summaries)
        ) + '</main></body></html>'
    )
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": 390, "height": 844}, color_scheme=scheme
            )
            page.set_content(html)
            refs = []
            for i, label in enumerate(LABELS):
                details = page.locator(f"#test-{i}")
                summary = details.locator("summary")
                expect(summary).to_have_text(label)
                closed = summary.evaluate(
                    """el => ({
                        listType: getComputedStyle(el).listStyleType,
                        marker: getComputedStyle(el, '::marker').content,
                        leftGap: el.querySelector('strong').getBoundingClientRect().left -
                                 el.getBoundingClientRect().left
                    })"""
                )
                assert closed["listType"] == "disclosure-closed"
                assert closed["leftGap"] > 0, (label, closed)
                refs.append(closed)
                summary.focus()
                summary.press("Enter")
                expect(details).to_have_attribute("open", "")
                assert summary.evaluate(
                    "el => getComputedStyle(el).listStyleType"
                ) == "disclosure-open"
                summary.press("Enter")
                expect(details).not_to_have_attribute("open", "")
            for current in refs[1:]:
                assert current == refs[0], (scheme, refs)
        finally:
            browser.close()
