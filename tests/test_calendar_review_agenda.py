"""Chronological calendar review and safe CSV export regressions."""
import csv
from datetime import date
from io import StringIO
from pathlib import Path

from fastapi.testclient import TestClient
from jinja2 import Environment

from app.main import app
from app.routers.calendar import calendar_review_items, _calendar_csv_safe


ROOT = Path(__file__).resolve().parents[1]


def test_review_items_are_month_scoped_chronological_and_planned_only():
    days = [
        {
            "date": date(2026, 11, 3),
            "in_month": True,
            "events": [
                {"status": "upcoming", "name": "Late", "dose_time": "20:00"},
                {"status": "recorded", "name": "Matched", "dose_time": "07:00"},
                {"status": "due", "name": "Early", "dose_time": "08:00"},
                {"status": "extra", "name": "Unmatched actual", "dose_time": "11:00"},
            ],
        },
        {
            "date": date(2026, 11, 1),
            "in_month": True,
            "events": [
                {"status": "unrecorded", "name": "Older", "dose_time": ""},
            ],
        },
        {
            "date": date(2026, 10, 31),
            "in_month": False,
            "events": [{"status": "unrecorded", "name": "Outside"}],
        },
    ]

    actual = calendar_review_items(days)
    assert [(row["date"].isoformat(), row["event"]["name"]) for row in actual] == [
        ("2026-11-01", "Older"),
        ("2026-11-03", "Early"),
        ("2026-11-03", "Late"),
    ]

    assert calendar_review_items([
        {"date": date(2026, 11, 1), "in_month": True, "events": []}
    ]) == []


def test_review_csv_escapes_spreadsheet_formula_inputs():
    for malicious in (
        "=SUM(1,1)",
        "+cmd",
        "-1+2",
        "@SUM",
        "  =2+3",
        "\t=2+3",
        "\n=2+3",
    ):
        assert _calendar_csv_safe(malicious) == "'" + malicious

    assert _calendar_csv_safe("Compound A") == "Compound A"
    assert _calendar_csv_safe(None) == ""
    assert _calendar_csv_safe(2.5) == "2.5"


def test_review_list_template_preserves_handoff_and_semantics():
    template = (ROOT / "app/templates/calendar.html").read_text()
    Environment().parse(template)

    for marker in (
        'id="calendar-review-agenda"',
        'class="calendar-review-row"',
        'id="calendar-agenda-summary"',
        'id="calendar-review-export"',
        'data-calendar-status="{{ x.status }}"',
        '/calendar/review.csv?month=',
        'href="/doses?compound_id={{ x.compound_id }}',
        'href="/dose-workspace?compound_id={{ x.compound_id }}',
        "No matching log",
        "A missing log does not establish",
    ):
        assert marker in template, marker


def test_review_month_page_and_csv_get_only():
    with TestClient(app) as client:
        page = client.get("/calendar?month=2026-11")
        assert page.status_code == 200
        assert 'id="calendar-review-agenda"' in page.text
        assert 'href="/calendar/review.csv?month=2026-11"' in page.text

        response = client.get("/calendar/review.csv?month=2026-11")
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/csv")
        assert 'tracker-calendar-review-2026-11.csv' in response.headers.get(
            "content-disposition", ""
        )
        rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
        assert rows[0] == [
            "Date", "Time", "Status", "Protocol", "Compound",
            "Planned amount", "Unit",
        ]
        assert all(len(row) == 7 for row in rows)
        assert all(row[2] in ("No matching log", "Due today", "Upcoming")
                   for row in rows[1:])


def test_review_filters_synchronize_without_backend_writes():
    script = (ROOT / "app/static/js/tracker-calendar-workbench.js").read_text()
    assert "reviewRows" in script
    assert "row.hidden = !show" in script
    assert "visibleReview" in script
    assert "fetch(" not in script
    assert ".submit(" not in script


def test_review_csv_route_sanitizes_names_from_projection(monkeypatch):
    from app.routers import calendar as calendar_router

    def fake_events(shown, db):
        return (
            date(2026, 11, 1),
            date(2026, 12, 1),
            {
                date(2026, 11, 5): [
                    {
                        "status": "due",
                        "dose_time": "09:00",
                        "protocol": "=SUM(1,2)",
                        "name": "@outside",
                        "amount_value": 2.5,
                        "amount_unit": "mg",
                    },
                    {
                        "status": "recorded",
                        "dose_time": "10:00",
                        "protocol": "Already matched",
                        "name": "Skip this",
                    },
                ]
            },
            [],
        )

    monkeypatch.setattr(calendar_router, "_month_events", fake_events)

    with TestClient(app) as client:
        response = client.get("/calendar/review.csv?month=2026-11")

    rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 2
    assert rows[1] == [
        "2026-11-05", "09:00", "Due today", "'=SUM(1,2)",
        "'@outside", "2.5", "mg",
    ]
