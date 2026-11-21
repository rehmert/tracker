"""Release 726: compact mobile lab navigation and usable filter controls."""
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "app/templates/labs.html"
CSS = ROOT / "app/static/css/tracker-labs-overview.css"


def actions_markup(cards, reports):
    text = HTML.read_text(encoding="utf-8")
    begin = text.index('<nav class="row tracker-flow696-actions labs726-actions"')
    end = text.index("</nav>", begin) + len("</nav>")
    return Environment().from_string(text[begin:end]).render(
        cards=cards, reports=reports
    )


def test_726_visible_mobile_actions_and_optional_tools_have_unique_targets():
    source = HTML.read_text(encoding="utf-8")
    Environment().parse(source)
    assert source.count('class="row tracker-flow696-actions labs726-actions"') == 1
    assert source.count("<summary>More lab tools</summary>") == 1
    assert source.index('href="#labs-reports-section"') < source.index(
        '<summary>More lab tools</summary>')
    assert source.index('</nav>') < source.index('id="labs-reports-section"')
    empty = actions_markup([], [])
    assert empty.count('href="/labs/new"') == 1
    assert empty.count('href="#labs-reports-section"') == 1
    assert empty.count('href="/labs/compare"') == 1
    assert 'href="#lab-trends-section"' not in empty
    assert 'copy_from=' not in empty
    filled = actions_markup([SimpleNamespace(name="TSH")],
                            [SimpleNamespace(id=42)])
    for destination in ('/labs/new', '#labs-reports-section',
                        '#lab-trends-section', '/labs/compare',
                        '/labs/new?copy_from=42'):
        assert filled.count('href="' + destination + '"') == 1, destination


def test_726_filters_keep_read_only_ids_and_phone_touch_css():
    html = HTML.read_text(encoding="utf-8")
    for identifier in ("labs-report-search", "labs-reports-sort",
                       "labs-reports-clear", "labs-reports-table",
                       "labs-analyte-search", "labs-range-filter",
                       "labs-trend-sort", "labs-trend-clear"):
        assert html.count('id="' + identifier + '"') == 1, identifier
    css = CSS.read_text(encoding="utf-8")
    assert 'tracker-labs-overview.css?v=726' in html
    assert 'tracker-labs-overview.css?v=20261109-527' not in html
    assert ".labs-reports-controls .field select" in css
    assert ".labs726-actions > .labs726-more" in css
    assert "min-height:48px" in css
    assert css.count("{") == css.count("}")
