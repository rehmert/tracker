"""Release 628 PK Simulator simplification contracts.

Protect legacy IDs, source assets, required graph controls and the
strictly read-only nature of the presentation enhancements.
"""
from html.parser import HTMLParser
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/pk.html"
CSS = ROOT / "app/static/css/tracker-pk-simple628.css"
JS = ROOT / "app/static/js/tracker-pk-simple628.js"


class MarkupAudit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.details = []
        self.details_stack = []
        self.graph_controls_in_details = False
        self.schedules_in_help = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        css_class = values.get("class", "").split()
        if tag == "details":
            self.details_stack.append(css_class)
            self.details.append(css_class)
        identifier = values.get("id")
        if identifier:
            self.ids.append(identifier)
            if identifier == "pkGraphLayerControls":
                self.graph_controls_in_details = any(
                    "pk628-graph-options" in c for c in self.details_stack
                )
            if identifier == "pkMultiSchedules":
                self.schedules_in_help = any(
                    "pk628-schedule-help" in c for c in self.details_stack
                )

    def handle_endtag(self, tag):
        if tag == "details" and self.details_stack:
            self.details_stack.pop()


def test_628_template_parses_and_preserves_pk_control_ids():
    source = TEMPLATE.read_text()
    Environment().parse(source)
    audit = MarkupAudit()
    audit.feed(source)
    assert len(audit.ids) == len(set(audit.ids))
    assert audit.graph_controls_in_details
    assert not audit.schedules_in_help
    assert any("pk628-schedule-help" in c for c in audit.details)
    for identifier in (
        "protocol", "compound", "half", "abs", "refresh", "back",
        "forward", "plot", "scenario", "save", "update", "remove",
        "wiStages", "wiPreview", "pkMultiSchedules", "pkMultiRun",
        "pkGraphLayerControls", "pkZoomIn", "pkZoomOut", "pkExportAnalysis",
        "pkResults", "pk628GraphHint",
    ):
        assert audit.ids.count(identifier) == 1, identifier
    assert source.count('data-pk-mode=') == 4
    assert "<ol class=\"pk628-steps\">" in source
    assert 'href="/static/css/tracker-pk-simple628.css?v=628"' in source
    assert 'src="/static/js/tracker-pk-simple628.js?v=628"' in source


def test_628_graph_orientation_is_presentation_only():
    js = JS.read_text()
    css = CSS.read_text()
    assert "tracker:pk-graph-updated" in js
    assert "window.trackerPkLastGraph" in js
    assert "textContent" in js
    assert "fetch(" not in js
    assert "localStorage" not in js
    assert "sessionStorage" not in js
    assert "innerHTML" not in js
    assert "createElement" not in js
    assert "@media(max-width:700px)" in css
    assert "pk628-graph-guide" in css
    assert "pk628-graph-options" in css
    assert "prefers-reduced-motion" in css


def test_628_browser_coverage_keeps_existing_qualified_module():
    smoke = (ROOT / "tests/browser/test_pk_smoke_281.py").read_text()
    runner = (ROOT / "scripts/tracker-browser-qualify.sh").read_text()
    assert "Release 628" in smoke
    assert "pk628-steps li" in smoke
    assert "pk628-graph-options" in smoke
    assert '"width": 390' in smoke
    assert runner.count("tests/browser/test_pk_smoke_281.py") == 1
