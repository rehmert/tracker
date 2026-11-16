"""Release 664: phone Chromium navigation using the shipped Jinja page body/CSS.

The browser document is an isolated rendered Workout Calendar view; no live
Tracker server or database mutation. FastAPI and SQLite are tested separately.
"""
import calendar
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from playwright.sync_api import expect, sync_playwright

from app.templating import templates

ROOT = Path(__file__).resolve().parents[2]
PAGE = (ROOT / "app/templates/workout_calendar664.html").read_text(
    encoding="utf-8"
)
BODY = PAGE.split("{% block content %}", 1)[1].rsplit("{% endblock %}", 1)[0]
CSS = (ROOT / "app/static/css/tracker-workout-calendar664.css").read_text(
    encoding="utf-8"
)
URL = "https://tracker.test/workouts/calendar?month=2024-02"


def mock_document664():
    month = date(2024, 2, 1)
    recorded = {
        date(2024, 2, 29): [
            SimpleNamespace(
                session_id=88, started_at=datetime(2024, 2, 29, 18),
                completed_at=datetime(2024, 2, 29, 19), set_count=2,
            ),
            SimpleNamespace(
                session_id=87, started_at=datetime(2024, 2, 29, 8),
                completed_at=datetime(2024, 2, 29, 9), set_count=1,
            ),
        ],
        date(2024, 2, 5): [
            SimpleNamespace(
                session_id=77, started_at=datetime(2024, 2, 5, 9),
                completed_at=datetime(2024, 2, 5, 10), set_count=1,
            ),
        ],
    }
    weeks = [
        [
            {
                "day": day,
                "in_month": day.month == month.month and day.year == month.year,
                "count": len(recorded.get(day, ())),
                "is_today": day == date(2024, 2, 16),
            }
            for day in week
        ]
        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(
            month.year, month.month,
        )
    ]
    days = [
        {
            "day": day, "sessions": recorded[day],
            "sets": sum(s.set_count for s in recorded[day]),
        }
        for day in sorted(recorded, reverse=True)
    ]
    html = templates.env.from_string(BODY).render(
        workout_calendar={
            "month": month, "month_label": "February 2024",
            "previous": "2024-01", "next": "2024-03",
            "sessions": 3, "training_days": 2, "sets": 4,
            "weeks": weeks, "days": days,
        },
    )
    return (
        '<!doctype html><html><head>'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>*{box-sizing:border-box}body{margin:0;padding:12px}'
        + CSS + '</style></head><body>' + html + '</body></html>'
    )


@pytest.mark.browser
@pytest.mark.parametrize("width,height", [(320, 740), (390, 844), (393, 852)])
def test_664_phone_month_grid_jump_to_two_session_day_and_summary_links(width, height):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height},
            is_mobile=True, has_touch=True, device_scale_factor=3,
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/workouts/calendar*", lambda route: route.fulfill(
            status=200, content_type="text/html", body=mock_document664(),
        ))
        try:
            page.goto(URL)
            expect(page.get_by_role("heading", name="Workout Calendar")).to_be_visible()
            expect(page.get_by_role("heading", name="February 2024")).to_be_visible()
            expect(page.get_by_role("link", name="Previous Month")).to_have_attribute(
                "href", "/workouts/calendar?month=2024-01"
            )
            expect(page.get_by_role("link", name="Next Month")).to_have_attribute(
                "href", "/workouts/calendar?month=2024-03"
            )
            expect(page.locator(".workout664-grid tbody tr")).to_have_count(5)
            expect(page.locator('[data-date664="2024-02-29"]')).to_be_visible()
            assert page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth"
            ), f"Workout calendar overflows {width}px"

            day = page.get_by_role(
                "link", name="2 completed sessions on 2024-02-29"
            )
            expect(day).to_have_attribute(
                "href", "#workout664-day-2024-02-29"
            )
            day.click()
            assert page.evaluate("location.hash") == "#workout664-day-2024-02-29"
            destination = page.locator("#workout664-day-2024-02-29")
            expect(destination).to_be_visible()
            expect(destination.locator("li")).to_have_count(2)
            expect(destination.locator(
                'a[href="/workouts/sessions/88/review"]'
            )).to_be_visible()
            expect(destination.locator(
                'a[href="/workouts/sessions/87/review"]'
            )).to_be_visible()
            assert not errors, errors
        finally:
            context.close()
            browser.close()
