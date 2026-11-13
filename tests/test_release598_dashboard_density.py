"""Release 598: dashboard density and pagination source contracts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_598_explanations_are_accessible_and_unmodified_content_can_expand():
    base = (ROOT / "app/templates/base.html").read_text()
    css = (ROOT / "app/static/css/tracker-section-explanations598.css").read_text()
    js = (ROOT / "app/static/js/tracker-section-explanations598.js").read_text()
    assert 'tracker-section-explanations598.css?v=598' in base
    assert 'tracker-section-explanations598.js?v=598' in base
    assert 'main section > p.note' in js
    assert "paragraph.closest('[role=\"alert\"]')" in js
    assert 'while (paragraph.firstChild) content.appendChild(paragraph.firstChild)' in js
    assert 'toggle.setAttribute(\'aria-controls\', content.id)' in js
    assert 'toggle.setAttribute(\'aria-expanded\', \'false\')' in js
    assert "entry.content.scrollHeight <= entry.content.clientHeight + 1" in js
    assert "requestAnimationFrame(update)" in js
    assert "'More'" in js and "'Less'" in js
    assert "-webkit-line-clamp: 1" in css
    assert "tracker-explanation598-open .tracker-explanation598-text" in css
    assert "[hidden]" in css


def test_598_dashboard_vial_page_sizes_controls_and_search():
    template = (ROOT / "app/templates/dashboard.html").read_text()
    css = (ROOT / "app/static/css/tracker-dashboard-vial-pages598.css").read_text()
    js = (ROOT / "app/static/js/tracker-dashboard-vial-pages598.js").read_text()
    assert template.count('data-inventory-pages598') == 1
    assert template.count('data-inventory-size598') == 1
    for option in ('5', '10', '25', '50', 'all'):
        expected = f'<option value="{option}"'
        assert expected in template
    assert '<option value="5" selected>' in template
    assert 'data-inventory-prev598' in template
    assert 'data-inventory-next598' in template
    assert 'data-inventory-status598 aria-live="polite"' in template
    assert "inventory-rows" in template
    assert 'tracker-dashboard-vial-pages598.js?v=598' in template
    assert 'tracker-dashboard-vial-pages598.css?v=598' in template
    assert "search?.addEventListener('input'" in js
    assert "page = 0; render()" in js
    assert "row.hidden = !visible.has(row)" in js
    assert "sizeInput.value === 'all'" in js
    assert "Math.ceil(matches.length / size)" in js
    assert 'aria-label="Dashboard vial stock pages"' in template
    assert "#inventory-rows > tr[hidden]" in css


def test_598_browser_gate_contains_real_http_and_https_ui_interactions():
    browser = (ROOT / "tests/browser/test_strict_csrf521.py").read_text()
    gate = (ROOT / "scripts/tracker-browser-qualify.sh").read_text()
    marker = "def test_598_explanation_expand_and_vial_pages("
    assert browser.count(marker) == 1
    before, body = browser.split(marker, 1)
    assert '@pytest.mark.parametrize("scheme", ("http", "https"))' in before[-140:]
    for phrase in (
        'page.set_viewport_size({"width": 600, "height": 850})',
        'page.locator(".tracker-explanation598-toggle:visible").first',
        'more.click()',
        'page.add_script_tag(url=base + "/static/js/tracker-dashboard-vial-pages598.js?v=598")',
        'selector.select_option("10")',
        'selector.select_option("all")',
        '.fill("vial 11")',
        'assert not errors, errors',
    ):
        assert phrase in body
    assert gate.count("-n 4 --dist=loadfile") == 3
    assert 'tests/browser/test_strict_csrf521.py' in gate
