"""Page-specific compact spacing stays scoped and non-destructive."""

from pathlib import Path
import re

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
COMPACT = ROOT / "app/static/css/tracker-compact-layout.css"
BASE = ROOT / "app/templates/base.html"


def css():
    return COMPACT.read_text()


def test_asset_version_and_source_order():
    base = BASE.read_text()
    assert base.count(
        "/static/css/tracker-compact-layout.css?v=batch39"
    ) == 1
    assert base.index(
        "tracker-compact-layout.css?v=batch39"
    ) > base.index("tracker-page-navigation.css")
    Environment().parse(base)


def test_page_navigation_is_compact():
    source = css()
    assert "#main-content .tracker-page-jump {" in source
    assert "#main-content .tracker-page-jump select {" in source
    assert "#main-content .tracker-copy-section-link {" in source


def test_protocol_filters_are_compact():
    source = css()
    assert "#main-content .tracker-protocol-tools" in source
    assert "#main-content .tracker-schedule-tools" in source
    assert "margin: .45rem 0 .55rem;" in source


def test_lab_cards_and_controls_are_compact():
    source = css()
    for marker in (
        "#main-content .labs-overview-counts",
        "#main-content .labs-overview-controls",
        "#main-content .labs-reports-controls",
        "#main-content .labgrid",
        "#main-content .labcard .latest",
    ):
        assert marker in source, marker


def test_dashboard_attention_and_status_are_compact():
    source = css()
    for marker in (
        "#main-content .tracker-attention-link",
        "#main-content .tracker-attention-header",
        "#main-content .tracker-status-grid",
        "#main-content .tracker-status-card",
        "#main-content .dashboard-action",
    ):
        assert marker in source, marker


def test_every_noncomment_rule_is_compact_scoped():
    source = css()
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    selectors = re.findall(r"([^{}]+)\{[^{}]*\}", source)

    # All actual rules must be rooted in the compact preference.
    for group in selectors:
        if "@" in group:
            continue
        for selector in group.split(","):
            selector = selector.strip()
            assert selector.startswith(
                ':root[data-density="compact"]'
            ), selector


def test_no_content_hiding_or_global_typography():
    source = css()
    for forbidden in (
        "display: none",
        "visibility: hidden",
        "overflow: hidden",
        "font-size: 0",
        "transform: scale(",
    ):
        assert forbidden not in source

    assert "min-height: 2.5rem;" in source
    assert "max-width: 760px" in source


def test_no_backend_modifications_required():
    base = BASE.read_text()
    assert '{% block content %}{% endblock %}' in base
    assert 'data-density-choice="compact"' in base
