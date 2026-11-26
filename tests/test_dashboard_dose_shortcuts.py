"""Dashboard uses the same authoritative scheduled entry as Today and Calendar."""
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from html import unescape
import re
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "app/templates/dashboard.html"
WORKSPACE = ROOT / "app/templates/dose_workspace.html"


def test_dashboard_template_parses():
    Environment().parse(DASHBOARD.read_text())


def test_shared_scheduled_action_links_to_quick_dose_for_due_not_future():
    source = (ROOT / "app/templates/_ui790.html").read_text()
    macro = Environment(autoescape=True).from_string(source).module.scheduled_action
    day = date(2026, 11, 2)
    event = {"protocol_item_id": 12, "compound_id": 7, "status": "due"}
    result = macro(event, day, "dashboard")
    url = urlsplit(unescape(re.search(r'href="([^"]+)"', result).group(1)))
    assert url.path == "/calendar/log-dose"
    assert parse_qs(url.query) == {"protocol_item_id": ["12"], "scheduled_on": ["2026-11-02"], "return_to": ["dashboard"]}
    future = macro(dict(event, status="upcoming"), day, "dashboard")
    assert "/calendar?month=2026-11#calendar-day-2026-11-02" in future
    assert "Log this dose" not in future
    pending = macro(dict(event, status="pending_review"), day, "dashboard")
    assert "/calendar#google-protocol-review783" in pending
    assert "Log this dose" not in pending


def test_dashboard_uses_shared_component_for_today_and_upcoming():
    source = DASHBOARD.read_text()
    assert "scheduled_action(e, now_date, 'dashboard')" in source
    assert "scheduled_action(e, day, 'dashboard')" in source
    assert 'data-dashboard-dose-handoff="1"' not in source


def test_workspace_accepts_planned_context():
    text = WORKSPACE.read_text()
    assert "planned_params.items()" in text
    assert "vial_id={{ vial.id }}" in text
