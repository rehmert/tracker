"""Shared long-page navigation regression tests."""

from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def test_shared_layout_controls():
    base = (
        ROOT / "app/templates/base.html"
    ).read_text()

    assert base.count(
        'id="tracker-page-jump-slot"'
    ) == 1

    assert base.count(
        'id="main-content" tabindex="-1"'
    ) == 1

    assert "tracker-skip-link" in base
    assert "tracker-page-navigation.js" in base
    assert "tracker-page-navigation.css" in base


def test_section_navigation_is_read_only():
    js = (
        ROOT /
        "app/static/js/tracker-page-navigation.js"
    ).read_text()

    assert 'querySelectorAll("h2, h3")' in js
    assert "headings.length < 3" in js
    assert "scrollIntoView" in js
    assert "htmx:afterSwap" in js
    assert "prefers-reduced-motion" in js

    assert "fetch(" not in js
    assert "localStorage" not in js
    assert "XMLHttpRequest" not in js


def test_accessibility_and_responsive_styles():
    css = (
        ROOT /
        "app/static/css/tracker-page-navigation.css"
    ).read_text()

    assert ":focus-visible" in css
    assert "@media print" in css
    assert "max-width: 760px" in css
    assert "[hidden]" in css


def test_base_template_parses():
    templates.env.get_template("base.html")
