"""Read-only section links regression coverage."""

from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def test_shared_script_order():
    html = (
        ROOT / "app/templates/base.html"
    ).read_text()

    first = html.index(
        'src="/static/js/tracker-page-navigation.js'
    )
    second = html.index(
        'src="/static/js/tracker-section-deep-links.js'
    )

    assert first < second
    assert html.count(
        "tracker-section-deep-links.js"
    ) == 1


def test_section_link_behavior():
    source = (
        ROOT /
        "app/static/js/tracker-section-deep-links.js"
    ).read_text()

    for feature in (
        "tracker-section-",
        "history.replaceState",
        "window.location.hash",
        "decodeURIComponent",
        "scrollIntoView",
        "navigator.clipboard.writeText",
        "aria-live",
        "currentFromScroll",
        "htmx:afterSwap",
    ):
        assert feature in source

    assert "fetch(" not in source
    assert "localStorage" not in source
    assert "XMLHttpRequest" not in source


def test_responsive_styles():
    css = (
        ROOT /
        "app/static/css/tracker-page-navigation.css"
    ).read_text()

    assert ".tracker-copy-section-link" in css
    assert ":focus-visible" in css
    assert "max-width: 760px" in css


def test_templates_parse():
    templates.env.get_template("base.html")
