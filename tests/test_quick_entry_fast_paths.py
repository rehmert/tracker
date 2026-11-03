"""Quick Entry fast-path and keyboard regression tests."""

from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def test_direct_entry_links_have_real_targets():
    quick = read("app/templates/quick_entry.html")

    targets = {
        "/doses#quick-dose-entry": (
            "app/templates/doses.html",
            'id="quick-dose-entry"',
        ),
        "/vitals#quick-vitals-entry": (
            "app/templates/vitals.html",
            'id="quick-vitals-entry"',
        ),
        "/supplies#tracker-stock-section": (
            "app/templates/supplies.html",
            'id="tracker-stock-section"',
        ),
        "/purchases#new-purchase": (
            "app/templates/purchases.html",
            'id="new-purchase"',
        ),
    }

    for link, (path, anchor) in targets.items():
        assert f'href="{link}"' in quick
        assert anchor in read(path)


def test_original_action_links_retained():
    quick = read("app/templates/quick_entry.html")

    for path in (
        "/doses",
        "/vitals",
        "/supplies",
        "/vials",
    ):
        assert f'href="{path}"' in quick


def test_keyboard_actions():
    js = read("app/static/js/tracker-quick-entry.js")

    for token in (
        "event.key === 'Escape'",
        "event.key === 'ArrowDown'",
        "event.key === 'Enter'",
        "visible.length === 1",
        "visible[0].focus()",
        "window.location.assign",
        "search.value = ''",
    ):
        assert token in js


def test_read_only_interaction():
    js = read("app/static/js/tracker-quick-entry.js")

    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
        "requestSubmit(",
        ".submit(",
    ):
        assert forbidden not in js


def test_templates_parse():
    for name in (
        "quick_entry.html",
        "doses.html",
        "vitals.html",
        "supplies.html",
        "purchases.html",
    ):
        templates.env.get_template(name)
