from datetime import date, datetime, timedelta
from types import SimpleNamespace as NS
from app.today import schedule_summary


def protocol(start, active=True, name="Current"):
    compound = NS(name="Tirzepatide")
    item = NS(compound_id=1, compound=compound, amount_value=5.0,
              amount_unit="mg", freq_count=7.0, freq_period="interval")
    return NS(id=3, name=name, is_active=active, start_date=start,
              end_date=None, items=[item])


def logged(when, cid=1):
    return NS(taken_at=datetime.combine(when, datetime.min.time()),
              vial=NS(compound_id=cid, compound=NS(name="Tirzepatide")),
              entered_value=5.0, entered_unit="mg")


def test_today_matches_recorded_and_projects_next_week():
    day = date(2026, 10, 26)
    result = schedule_summary([protocol(day)], [logged(day)], day)
    assert result["today"][0]["status"] == "recorded"
    assert result["upcoming"][0][0] == day + timedelta(days=7)
    assert result["upcoming"][0][1]["status"] == "upcoming"


def test_today_ignores_what_if_and_reports_missing_start():
    day = date(2026, 10, 26)
    result = schedule_summary([protocol(day, active=False), protocol(None)], [], day)
    assert result["today"] == []
    assert result["upcoming"] == []
    assert result["missing_start"] == [{"id": 3, "name": "Current"}]


def test_today_unplanned_recorded_is_unscheduled():
    day = date(2026, 10, 26)
    result = schedule_summary([], [logged(day)], day)
    assert result["today"][0]["status"] == "extra"


def test_today_does_not_project_after_end_date():
    day = date(2026, 10, 26)
    p = protocol(day)
    p.end_date = day
    result = schedule_summary([p], [], day)
    assert len(result["today"]) == 1
    assert result["upcoming"] == []
