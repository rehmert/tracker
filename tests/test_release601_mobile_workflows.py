"""Release 601: bundled navigation and mobile-workflow contracts.

These source checks are read-only. The guarded Chromium gate separately
exercises the live HTTP and HTTPS layouts and interactions.
"""
from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app/templates"
SCRIPTS = ROOT / "app/static/js"
CSS = ROOT / "app/static/css"


def test_601_legacy_section_links_and_unicode_slug_fixed():
    script = (SCRIPTS / "tracker-section-deep-links.js").read_text()
    # Python raw-string assertions ensure JavaScript gets one backslash,
    # not the formerly broken double-backslash regular expressions.
    assert r".replace(/[\u0300-\u036f]/g" in script
    assert r".replace(/\s+/g" in script
    assert r"/^tracker-section-(\d+)$/" in script
    for broken in (
        r".replace(/[\\u0300-\\u036f]/g",
        r".replace(/\\s+/g",
        r"/^tracker-section-(\\d+)$/",
    ):
        assert broken not in script
    base = (TEMPLATES / "base.html").read_text()
    assert base.count("tracker-section-deep-links.js?v=601") == 1
    assert "tracker-page-navigation.js" in base


def test_601_today_leads_with_scheduled_actions_and_all_upcoming_entries():
    today = (TEMPLATES / "mobile_today509.html").read_text()
    assert today.index('class="tracker-daily-glance601"') < today.index(
        'class="tracker-daily-actions"'
    )
    assert today.index('aria-labelledby="mobile-schedule-heading"') < today.index(
        'aria-labelledby="mobile-latest-heading"'
    )
    assert today.count("summary.upcoming[:8]") == 1
    assert today.count("summary.upcoming[8:]") == 1
    assert "summary.upcoming|length > 8" in today
    assert 'class="tracker-daily-upcoming-more601"' in today
    assert today.count('href="/doses?compound_id={{ item.compound_id }}') >= 3
    assert today.count("tracker-mobile-workflows601.css?v=601") == 1
    assert "Record Vitals" in today
    assert "Save Reading" in today
    templates.env.get_template("mobile_today509.html")


def test_601_vial_mobile_cards_use_canonical_rows_and_existing_workflows():
    vials = (TEMPLATES / "vials.html").read_text()
    script = (SCRIPTS / "tracker-vial-mobile601.js").read_text()
    assert "tracker-mobile-workflows601.css?v=601" in vials
    assert "tracker-vial-mobile601.js?v=601" in vials
    for marker in (
        'id="tracker-vials-sortable"',
        'id="tracker-vial-pager448"',
        'id="bulk-vials"',
        'id="bulk-editor-panel"',
        'id="tracker-vial-quick-find"',
        'class="bulk-vial-check"',
    ):
        assert marker in vials
    assert "querySelectorAll('tbody > tr')" in script
    assert "cell.dataset.label = labels[index]" in script
    assert "row.dataset.vialExpanded601" in script
    assert "table.classList.toggle('tracker-vials-as-cards601'" in script
    assert "localStorage.setItem(KEY, mode)" in script
    assert "form.submit(" not in script
    assert "fetch(" not in script
    assert "cloneNode(" not in script
    assert "innerHTML" not in script
    assert "removeChild(" not in script
    templates.env.get_template("vials.html")


def test_601_mobile_layout_preserves_full_table_and_available_actions():
    css = (CSS / "tracker-mobile-workflows601.css").read_text()
    assert "@media screen and (max-width: 760px)" in css
    assert "@media screen and (max-width: 359px)" in css
    assert "tracker-vials-as-cards601" in css
    assert "tbody > tr[hidden]" in css
    assert "display: none !important" in css
    assert "tracker-vial-detail-toggle601" in css
    assert "min-height: 44px" in css
    assert "tracker-daily-upcoming-more601" in css
    assert "tracker-daily-glance601" in css
    assert css.count("{") == css.count("}")


def test_601_real_browser_gate_covers_mobile_and_desktop_views():
    browser = (ROOT / "tests/browser/test_strict_csrf521.py").read_text()
    for name in (
        "test_601_mobile_vial_cards_preserve_table_controls",
        "test_601_mobile_today_and_legacy_section_navigation",
    ):
        assert browser.count("def " + name + "(") == 1
        preceding = browser.split("def " + name + "(", 1)[0]
        assert '@pytest.mark.parametrize("scheme", ("http", "https"))' in preceding[-110:]
    assert "set_viewport_size" in browser
    assert "tracker-vials-as-cards601" in browser
    assert "tracker-heading-creme-brulee" in browser
