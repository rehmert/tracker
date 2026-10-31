"""Stage 27 vial date visibility tests."""

import ast
from pathlib import Path

from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[1]

ROUTER = ROOT / "app/routers/doses.py"
TEMPLATE = ROOT / "app/templates/dose_workspace.html"


def test_router_parses():
    ast.parse(ROUTER.read_text())


def test_template_parses():
    Environment().parse(TEMPLATE.read_text())


def test_date_columns_present():
    source = TEMPLATE.read_text()

    # Accept plain or accessible sortable table headers.
    from html.parser import HTMLParser

    class HeaderParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_header = False
            self.headers = []
            self.current = []

        def handle_starttag(self, tag, attrs):
            if tag == "th":
                self.in_header = True
                self.current = []

        def handle_data(self, data):
            if self.in_header:
                self.current.append(data)

        def handle_endtag(self, tag):
            if tag == "th" and self.in_header:
                self.headers.append(
                    "".join(self.current).strip()
                )
                self.in_header = False

    parser = HeaderParser()
    parser.feed(source)

    assert "First used" in parser.headers
    assert "Beyond-use" in parser.headers
    assert "Expires" in parser.headers


def test_missing_dates_are_explicit():
    source = TEMPLATE.read_text()

    assert "Not recorded" in source


def test_date_context_passed():
    source = ROUTER.read_text()

    assert "vial_date_details=vial_date_details" in source


def test_recommendation_explanation_present():
    source = TEMPLATE.read_text()

    assert "recommended_reason" in source


def test_vial_recording_link_preserved():
    source = TEMPLATE.read_text()

    assert "vial_id={{ vial.id }}" in source


def test_calendar_handoff_preserved():
    source = TEMPLATE.read_text()

    assert "planned_params.items()" in source


def test_search_preserved():
    source = TEMPLATE.read_text()

    assert "tracker-vial-search" in source
