from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "app/static/css/tracker-headings531.css"
HTML = ROOT / "app/templates/base.html"


def test_headings531_loaded_after_spacing530():
    html = HTML.read_text()
    assert html.count("tracker-headings531.css?v=531") == 1
    assert html.index("tracker-spacing-dense.css?v=1") < html.index(
        "tracker-headings531.css?v=531"
    )
    Environment().parse(html)


def test_headings531_only_changes_h1():
    css = CSS.read_text()
    assert css.count("{") == css.count("}") == 3
    assert "#main-content h1" in css
    assert "#main-content .dashboard-hero h1" in css
    assert "#main-content .tracker-daily-hero h1" in css
    assert css.count("font-size:") == 3
    assert "h2 {" not in css
    assert "h3 {" not in css
    assert "margin:" not in css
    assert "padding:" not in css
    assert "!important" not in css
