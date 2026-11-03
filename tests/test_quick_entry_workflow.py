"""Quick Entry hub: navigation-only workflow."""

from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def test_original_actions_preserved():
    html = read("app/templates/quick_entry.html")

    for href, label in (
        ("/doses", "Record dose"),
        ("/vitals", "Record vitals"),
        ("/supplies", "Record supply usage"),
        ("/vials", "Record vial preparation"),
    ):
        assert f'href="{href}"' in html
        assert label in html


def test_additional_workflows():
    html = read("app/templates/quick_entry.html")

    for route in (
        "/calendar",
        "/dose-workspace",
        "/consumption",
        "/labs",
        "/purchases",
        "/pages",
    ):
        assert f'href="{route}"' in html


def test_accessible_action_search():
    html = read("app/templates/quick_entry.html")
    js = read("app/static/js/tracker-quick-entry.js")

    for marker in (
        "data-quick-search",
        "data-quick-reset",
        "data-quick-count",
        "data-quick-empty",
        "data-quick-action",
        'aria-live="polite"',
    ):
        assert marker in html

    for marker in (
        "action.hidden = !show",
        "aria-pressed",
        "event.key !== '/'",
        "search.focus()",
    ):
        assert marker in js


def test_read_only():
    js = read("app/static/js/tracker-quick-entry.js")
    html = read("app/templates/quick_entry.html")

    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
        "requestSubmit(",
        ".submit(",
    ):
        assert forbidden not in js

    assert "<form" not in html
    assert 'method="post"' not in html


def test_template_parses():
    templates.env.get_template("quick_entry.html")
