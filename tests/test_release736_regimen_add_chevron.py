"""Release 736: visible, stateful chevrons on Regimen Add disclosures."""
from pathlib import Path
import re

import pytest
from jinja2 import Environment
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/regimen635.html"
APP_CSS = ROOT / "app/static/app.css"
LABELS = ("Add supplement or medication", "Add schedule")


def markup():
    source = TEMPLATE.read_text(encoding="utf-8")
    Environment().parse(source)
    css = source.split("<style>", 1)[1].split("</style>", 1)[0]
    summaries = []
    for label in LABELS:
        match = re.search(
            r"<summary class=\"reg733-add-trigger\"><strong>"
            + re.escape(label) + r"</strong></summary>", source
        )
        assert match is not None, label
        summaries.append(match.group(0))
    assert "summary.reg733-add-trigger::after" in css
    assert "details[open]>summary.reg733-add-trigger::after" in css
    assert "summary.reg733-add-trigger::-webkit-details-marker" in css
    return (
        '<!doctype html><html><head>'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<style>" + APP_CSS.read_text(encoding="utf-8") + "</style>"
        "<style>" + css + "</style>"
        '</head><body><main id="main-content">'
        '<section class="card"><details id="test-medication">'
        + summaries[0]
        + '<div><input aria-label="Medication name" value="Example"/></div>'
        + '</details></section><section class="card">'
        + '<details id="test-schedule">' + summaries[1]
        + '<div><input aria-label="Scheduled time" value="08:30"/></div>'
        + '</details></section></main></body></html>'
    )


def test_736_template_add_disclosures_still_use_semantic_native_details():
    html = markup()
    for label in LABELS:
        assert label in html
    assert 'data-reg733-edit' not in html
    assert html.count('<summary class="reg733-add-trigger">') == 2


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
            for detail_id, label in (
                ("test-medication", LABELS[0]),
                ("test-schedule", LABELS[1]),
            ):
                details = page.locator(f"#{detail_id}")
                summary = details.locator("summary")
                expect(summary).to_have_text(label)
                expect(details).not_to_have_attribute("open", "")
                assert summary.evaluate(
                    "el => el.getBoundingClientRect().height >= 44"
                ), (width, scheme, label)
                closed = summary.evaluate(
                    """el => {
                        const p = getComputedStyle(el, '::after');
                        return {
                            content: p.content,
                            width: parseFloat(p.width),
                            border: p.borderRightWidth,
                            display: p.display,
                            color: p.borderRightColor,
                            text: getComputedStyle(el).color,
                            transform: p.transform
                        };
                    }"""
                )
                assert closed["content"] == '""', closed
                assert closed["width"] >= 8, closed
                assert closed["border"] == "2px", closed
                assert closed["display"] == "block", closed
                assert closed["color"] == closed["text"], closed

                summary.click()
                expect(details).to_have_attribute("open", "")
                # Disable animations after opening so the computed transform
                # is the final upward-pointing chevron, not a mid-transition frame.
                page.add_style_tag(content="summary.reg733-add-trigger::after {transition:none!important}")
                opened = summary.evaluate(
                    "el => getComputedStyle(el, '::after').transform"
                )
                assert opened != closed["transform"], (width, scheme, label)
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                ), (width, scheme)
                summary.click()
                expect(details).not_to_have_attribute("open", "")
        finally:
            browser.close()
