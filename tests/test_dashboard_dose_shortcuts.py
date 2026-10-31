"""Dashboard scheduled-dose navigation regression tests."""

import html
import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "app/templates/dashboard.html"
WORKSPACE = ROOT / "app/templates/dose_workspace.html"


def source():
    return DASHBOARD.read_text()


def shortcuts():
    return re.findall(
        r'<a class="tag" '
        r'data-dashboard-dose-handoff="1" '
        r'href="([^"]+)">'
        r'Choose vial first</a>',
        source(),
    )


def test_dashboard_template_parses():
    Environment().parse(source())


def test_two_shortcuts_exist():
    assert len(shortcuts()) == 2


def test_shortcuts_use_workspace():
    for url in shortcuts():
        assert url.startswith("/dose-workspace?")


def test_shortcuts_preserve_calendar_parameters():
    for url in shortcuts():
        for parameter in (
            "compound_id",
            "planned_date",
            "planned_time",
            "planned_amount",
            "planned_unit",
        ):
            assert parameter + "=" in url


def test_existing_record_links_remain():
    text = source()

    assert text.count('">Log dose</a>') >= 2
    assert text.count(
        'data-dashboard-dose-handoff="1"'
    ) == 2


def test_today_and_upcoming_dates_are_distinct():
    first, second = shortcuts()

    assert "planned_date={{ now_date }}" in first
    assert "planned_date={{ day.isoformat() }}" in second


def test_workspace_accepts_planned_context():
    text = WORKSPACE.read_text()

    assert "planned_params.items()" in text
    assert "vial_id={{ vial.id }}" in text


def test_rendered_shortcuts_have_valid_query_parameters():
    env = Environment(autoescape=True)

    today = date(2026, 11, 2)
    upcoming = date(2026, 11, 5)

    event = SimpleNamespace(
        compound_id=7,
        dose_time="14:30",
        amount_value=2.5,
        amount_unit="mg",
    )

    for index, expected_date in enumerate(
        ("2026-11-02", "2026-11-05")
    ):
        template = env.from_string(shortcuts()[index])

        rendered = template.render(
            e=event,
            now_date=today,
            day=upcoming,
        )

        parsed = urlsplit(html.unescape(rendered))
        params = parse_qs(parsed.query)

        assert parsed.path == "/dose-workspace"
        assert params["compound_id"] == ["7"]
        assert params["planned_date"] == [expected_date]
        assert params["planned_time"] == ["14:30"]
        assert params["planned_amount"] == ["2.5"]
        assert params["planned_unit"] == ["mg"]
