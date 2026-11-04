"""Calendar day context and non-mutating workflow navigation."""

from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]

CALENDAR = ROOT / "app/templates/calendar.html"
WORKSPACE = ROOT / "app/templates/dose_workspace.html"
DOSES = ROOT / "app/templates/doses.html"

SUMMARY_JS = (
    ROOT / "app/static/js/tracker-calendar-day-context.js"
)
SUMMARY_CSS = (
    ROOT / "app/static/css/tracker-calendar-day-context.css"
)
WORKSPACE_JS = (
    ROOT / "app/static/js/tracker-workspace-34107.js"
)
DOSE_JS = (
    ROOT / "app/static/js/tracker-dose-handoff-34101.js"
)


def test_day_summary_assets_loaded():
    text = CALENDAR.read_text()

    assert "tracker-calendar-day-context.js" in text
    assert "tracker-calendar-day-context.css" in text
    assert 'id="calendar-grid"' in text
    assert 'data-calendar-date="{{ d.date.isoformat() }}"' in text


def test_planned_and_recorded_are_distinct():
    text = SUMMARY_JS.read_text()

    assert '"due", "upcoming", "unrecorded"' in text
    assert '"recorded", "extra"' in text
    assert 'planned + " planned"' in text
    assert 'recorded + " recorded"' in text
    assert "if (item.hidden) continue;" in text


def test_filtered_calendar_updates_summaries():
    text = SUMMARY_JS.read_text()

    assert 'search.addEventListener("input", update)' in text
    assert 'filter.addEventListener("change", update)' in text
    assert "queueMicrotask(update)" in text


def test_exact_day_navigation():
    text = SUMMARY_JS.read_text()
    assert "hashchange" in text
    assert "tracker-calendar-return-day" in text
    assert ":target" in SUMMARY_CSS.read_text()

    workspace = WORKSPACE_JS.read_text()
    dose = DOSE_JS.read_text()

    assert "'#calendar-day-'" in workspace
    assert "'#calendar-day-'" in dose

    assert "calendarLink.href = calendarReturn" in workspace
    assert "calendar.href =" in dose

    assert 'data-workspace-calendar-shortcut' in WORKSPACE.read_text()
    assert 'data-planned-calendar>' in DOSES.read_text()


def test_changes_are_read_only():
    text = SUMMARY_JS.read_text()

    for forbidden in (
        "fetch(",
        "requestSubmit(",
        "form.submit(",
    ):
        assert forbidden not in text

    server = (ROOT / "app/routers/doses.py").read_text()
    assert "idempotency.check(" in server
    assert "reserve_inventory_write" in server


def test_templates_parse():
    for path in (CALENDAR, WORKSPACE, DOSES):
        Environment().parse(path.read_text())
