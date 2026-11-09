"""Release 529: scoped vertical spacing without behavior changes."""

from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "app/templates/base.html"
CSS = ROOT / "app/static/css/tracker-spacing529.css"


def test_529_stylesheet_is_last_static_css():
    base = BASE.read_text()

    link = "/static/css/tracker-spacing529.css?v=529"
    previous = "/static/css/tracker-mobile-quick528.css?v=528"

    assert base.count(link) == 1
    assert base.index(previous) < base.index(link)
    assert base.index(link) < base.index("/ui/theme.css")

    Environment().parse(base)


def test_529_density_scope_and_no_content_hiding():
    css = CSS.read_text()

    assert ':root[data-density="balanced"]' in css
    assert ':root[data-density="compact"]' in css
    assert '[data-density="comfortable"]' not in css

    for forbidden in (
        "display: none",
        "visibility: hidden",
        "overflow: hidden",
        "position: fixed",
        "transform: scale(",
        "font-size:",
        "max-height:",
    ):
        assert forbidden not in css


def test_529_covers_shared_and_mobile_spacing():
    css = CSS.read_text()

    for marker in (
        "--density-section-gap",
        "--density-heading-gap",
        "#main-content h2",
        "#main-content h3",
        "#main-content .dashboard-panel",
        ".tracker-daily509",
        ".tracker-daily-section",
        ".tracker-daily-heading",
        ".tracker-daily-mode",
        ".tracker-daily-vitals",
        ".tracker-daily-list li",
        "min-height: 44px;",
    ):
        assert marker in css, marker


def test_529_existing_mobile_actions_preserved():
    base = BASE.read_text()
    daily = (
        ROOT / "app/templates/mobile_today509.html"
    ).read_text()

    assert "tracker-mobile-add528" in base
    assert "tracker-mobile-quick528" in base
    assert 'action="/vitals"' in daily
    assert 'data-daily-vitals-form' in daily
