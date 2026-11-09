from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "app/static/css/tracker-spacing-dense.css"
BASE = ROOT / "app/templates/base.html"


def test_dense_spacing_loaded_last():
    html = BASE.read_text()

    new = "tracker-spacing-dense.css?v=1"

    assert html.count(new) == 1
    assert html.index("tracker-spacing529.css") < html.index(new)
    assert html.index(new) < html.index("/ui/theme.css")

    Environment().parse(html)


def test_dense_spacing_only_affects_balanced_and_compact():
    css = CSS.read_text()

    assert ':root[data-density="balanced"]' in css
    assert ':root[data-density="compact"]' in css
    assert '[data-density="comfortable"]' not in css

    for forbidden in (
        "display: none",
        "visibility: hidden",
        "overflow: hidden",
        "position: fixed",
        "font-size:",
        "transform: scale(",
    ):
        assert forbidden not in css


def test_dense_spacing_targets_real_sections():
    css = CSS.read_text()

    for marker in (
        ".dashboard-panel",
        ".dashboard-metrics",
        ".tracker-attention",
        ".tracker-status-overview",
        ".today-card",
        ".protocol-card",
        ".chartbox",
        ".tracker-page-jump",
        ".tracker-daily509",
        ".tracker-daily-section",
        ".tracker-daily-heading",
        ".tracker-daily-list li",
        "min-height: 44px;",
    ):
        assert marker in css, marker


def test_dense_spacing_css_structure():
    css = CSS.read_text()
    assert css.count("{") == css.count("}")
    assert "@media (max-width: 760px)" in css
