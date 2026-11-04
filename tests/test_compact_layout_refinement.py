"""Batch 38: Compact density saves vertical space without hiding content."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]

BASE = ROOT / "app/templates/base.html"
APP_CSS = ROOT / "app/static/app.css"
COMPACT = ROOT / "app/static/css/tracker-compact-layout.css"
DENSITY = ROOT / "app/static/density.js"


def stylesheet():
    return COMPACT.read_text()


def test_stylesheet_is_loaded_last():
    base = BASE.read_text()

    link = "/static/css/tracker-compact-layout.css?v=batch39"

    assert base.count(link) == 1
    assert base.index(link) > base.index("tracker-page-navigation.css")
    assert base.index(link) < base.index("</head>")

    Environment().parse(base)


def test_existing_density_preferences_remain():
    js = DENSITY.read_text()
    app = APP_CSS.read_text()

    assert "'comfortable', 'balanced', 'compact'" in js
    assert 'dataset.density = value' in js
    assert ':root[data-density="comfortable"]' in app
    assert ':root[data-density="compact"]' in app


def test_refinement_only_targets_compact():
    css = stylesheet()

    assert ':root[data-density="compact"]' in css

    # Ensure no other density-specific selectors are overridden.
    assert '[data-density="comfortable"]' not in css
    assert '[data-density="balanced"]' not in css

    # Avoid unscoped rules affecting every density mode.
    assert not any(
        line.startswith(("main {", "body {", "html {"))
        for line in css.splitlines()
    )


def test_main_spacing_is_reduced():
    css = stylesheet()

    for marker in (
        "--density-main-top: .55rem;",
        "--density-main-bottom: 1.1rem;",
        "--density-section-gap: .65rem;",
        "--density-card-pad: .55rem;",
        "--density-cell-y: .25rem;",
        "--density-form-gap: .36rem;",
    ):
        assert marker in css, marker


def test_app_chrome_and_headings_are_compacted():
    css = stylesheet()

    for marker in (
        "#main-content > .workspace-toolbar",
        "#main-content > .ux-breadcrumbs",
        "#main-content > h1",
        "#main-content h2",
        "#main-content h3",
        "#main-content .ux-shortcuts",
        "#main-content .grid",
    ):
        assert marker in css, marker


def test_dashboard_and_dense_pages_are_covered():
    css = stylesheet()

    for marker in (
        "#main-content .dashboard-metrics > div",
        "#main-content .dashboard-panel",
        "#main-content .today-card",
        "#main-content .protocol-card",
        "#main-content .stats > div",
        "#main-content .chartbox",
        "#main-content th",
        "#main-content td",
    ):
        assert marker in css, marker


def test_content_remains_visible_and_tables_scroll():
    css = stylesheet()

    for forbidden in (
        "display: none",
        "visibility: hidden",
        "overflow: hidden",
        "position: fixed",
        "font-size: 0",
        "transform: scale(",
    ):
        assert forbidden not in css

    assert 'max-width: 760px' in css
    assert "min-height: 2.5rem;" in css

    app = APP_CSS.read_text()
    assert ".scroll { overflow-x:auto; }" in app


def test_no_backend_changes_required():
    base = BASE.read_text()

    assert '{% block content %}{% endblock %}' in base
    assert 'id="main-content"' in base
    assert 'id="workspace-settings"' in base
    assert 'data-density-choice="compact"' in base
