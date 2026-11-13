"""Stable section anchors and legacy compatibility."""

from pathlib import Path

from app.templating import templates


ROOT = Path(__file__).resolve().parents[1]


def javascript():
    return (
        ROOT /
        "app/static/js/tracker-section-deep-links.js"
    ).read_text()


def test_descriptive_heading_ids():
    js = javascript()

    assert "function headingSlug(value)" in js
    assert '"tracker-heading-" +' in js
    assert 'headingSlug(title)' in js
    assert "normalize(" in js


def test_existing_ids_preserved():
    js = javascript()

    assert "if (heading.id) return" in js
    assert "document.getElementById(candidate)" in js
    assert 'candidate = base + "-" + suffix++' in js


def test_legacy_links_supported():
    js = javascript()

    assert "function legacySectionTarget(id)" in js
    assert "tracker-section-" in js
    assert "legacySectionTarget(id)" in js
    assert "Number.isSafeInteger(index)" in js


def test_copy_and_scroll_still_available():
    js = javascript()

    for name in (
        "history.replaceState",
        "navigator.clipboard.writeText",
        "scrollIntoView",
        "currentFromScroll",
        "htmx:afterSwap",
    ):
        assert name in js


def test_global_script_version():
    html = (
        ROOT / "app/templates/base.html"
    ).read_text()

    # The global script must load the current, cache-busted Release 601
    # version so users do not keep the pre-fix legacy-anchor regexes.
    assert html.count("tracker-section-deep-links.js?v=601") == 1
    assert "tracker-section-deep-links.js?v=20261103-stable" not in html

    templates.env.get_template("base.html")
