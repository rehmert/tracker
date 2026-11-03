"""Quick Entry metric links and keyboard navigation."""

from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def test_metric_links_have_real_inputs():
    quick = read("app/templates/quick_entry.html")
    vitals = read("app/templates/vitals.html")

    for anchor in (
        "quick-vitals-weight",
        "quick-vitals-bp",
        "quick-vitals-pulse",
    ):
        assert f'href="/vitals#{anchor}"' in quick
        assert vitals.count(f'id="{anchor}"') == 1


def test_focus_is_explicit_and_read_only():
    vitals = read("app/templates/vitals.html")
    js = read(
        "app/static/js/tracker-vitals-quick-focus.js"
    )

    assert "tracker-vitals-quick-focus.js" in vitals
    assert "allowed.has(id)" in js
    assert "focusRequestedInput" in js
    assert "hashchange" in js

    for forbidden in (
        "fetch(",
        "localStorage",
        "sessionStorage",
        "requestSubmit(",
        ".submit(",
        ".value =",
    ):
        assert forbidden not in js


def test_card_navigation_skips_hidden_actions():
    js = read("app/static/js/tracker-quick-entry.js")

    for token in (
        "actions.forEach(action =>",
        "action.addEventListener('keydown'",
        "'ArrowUp'",
        "'ArrowDown'",
        "'Home'",
        "'End'",
        "item => !item.hidden",
        "visible[next].focus()",
    ):
        assert token in js


def test_original_workflows_remain():
    html = read("app/templates/quick_entry.html")

    for href in (
        "/doses",
        "/vitals",
        "/supplies",
        "/vials",
        "/calendar",
        "/dose-workspace",
    ):
        assert f'href="{href}"' in html


def test_templates_parse():
    templates.env.get_template("quick_entry.html")
    templates.env.get_template("vitals.html")
