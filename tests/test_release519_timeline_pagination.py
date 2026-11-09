"""Release 519: SQL-indexed Health Timeline equals the legacy renderer.

Synthetic, isolated in-memory SQLite only. No connection to DEV/PROD data.
"""
from collections import Counter
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import (
    Compound, DoseLog, LabReport, LabResult, Protocol, VitalReading, Vial,
)
from app.routers.health_timeline import (
    _timeline_context, EVENT_TYPES, RANGES,
)
from app.timeline_paged519 import paged_timeline_context


@pytest.fixture
def timeline_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        compound = Compound(name="Release 519 reference compound")
        vial = Vial(
            compound=compound, label="Reference vial",
            content_value=10, content_unit="mg",
        )
        db.add(vial)
        for index in range(61):
            day = date(2026, 11, 1) + timedelta(days=index % 9)
            at = datetime(day.year, day.month, day.day, index % 24, 0, 0)
            db.add(VitalReading(
                measured_at=at, weight_kg=80 + index,
                systolic=115, diastolic=70, pulse_bpm=65,
                context=f"context-{index}", notes=f"note-{index}",
            ))
            db.add(DoseLog(
                vial=vial, taken_at=at,
                entered_value=1.25, entered_unit="mg", amount_base=1250,
                kind="dose" if index % 3 else "waste",
                site="abdomen", notes=f"dose-note-{index}",
            ))
            lab = LabReport(
                drawn_on=day, lab_name=f"Lab draw {index}",
                notes=f"lab-note-{index}",
            )
            lab.results.append(
                LabResult(analyte="TSH", value=1.5, unit="mIU/L")
            )
            db.add(lab)
        # Same link/timestamp for both protocol event types, so their
        # title tie-breaking must match the legacy Python reverse sort.
        db.add(Protocol(
            name="Current plan", is_active=True,
            start_date=date(2026, 11, 8),
            end_date=date(2026, 11, 8),
        ))
        db.add(Protocol(
            name="Inactive draft (excluded)", is_active=False,
            start_date=date(2026, 11, 8),
            end_date=date(2026, 11, 8),
        ))
        db.add(Protocol(
            name="Old active plan", is_active=True,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 5),
        ))
        db.commit()
        yield db, engine
    engine.dispose()


def _new(db, *, days=0, event_type="all", page=1, page_size=25,
         start_date=date(2026, 11, 1), end_date=date(2026, 11, 9)):
    return paged_timeline_context(
        db, days=days, event_type=event_type,
        start_date=start_date, end_date=end_date,
        page=page, page_size=page_size,
        ranges=RANGES, event_types=EVENT_TYPES,
    )


@pytest.mark.parametrize("kind", list(EVENT_TYPES))
@pytest.mark.parametrize(("page", "page_size"), [
    (1, 25), (2, 25), (3, 25), (1, 50), (2, 50),
    (999, 25), (-10, 25), (1, 100),
])
def test_519_sql_page_matches_legacy_event_order_and_counts(
    timeline_db, kind, page, page_size,
):
    db, _ = timeline_db
    existing = _timeline_context(
        db, days=0, event_type=kind, q="",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 9),
    )
    actual = _new(db, event_type=kind, page=page, page_size=page_size)
    assert actual["counts"] == existing["counts"]
    assert actual["total"] == existing["total"]
    assert actual["matching"] == len(existing["events"])
    assert "Inactive draft" not in repr(actual["events"])
    total_pages = max(1, (len(existing["events"]) + page_size - 1) // page_size)
    expected_page = min(max(page, 1), total_pages)
    offset = (expected_page - 1) * page_size
    assert actual["page"] == expected_page
    assert actual["total_pages"] == total_pages
    assert actual["events"] == existing["events"][offset:offset + page_size]
    assert sum(len(x["events"]) for x in actual["groups"]) == len(actual["events"])


def test_519_sql_pagination_handles_custom_date_and_unbounded_all(timeline_db):
    db, _ = timeline_db
    cases = [
        (3650, None, None),
        (0, date(2026, 11, 8), None),
        (0, None, date(2026, 11, 2)),
        (0, date(2026, 11, 8), date(2026, 11, 8)),
    ]
    for days, first, last in cases:
        existing = _timeline_context(
            db, days=days, start_date=first, end_date=last,
        )
        actual = _new(
            db, days=days, start_date=first, end_date=last,
            page=1, page_size=100,
        )
        assert actual["total"] == existing["total"]
        assert actual["counts"] == existing["counts"]
        assert actual["events"] == existing["events"][:100]


def test_519_inverted_date_range_still_rejected(timeline_db):
    db, _ = timeline_db
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        _new(
            db,
            start_date=date(2026, 11, 9),
            end_date=date(2026, 11, 1),
        )
    assert error.value.status_code == 400


def test_519_page_reads_are_bounded_even_with_many_records(timeline_db):
    db, engine = timeline_db
    db.expunge_all()
    sql = []

    def trace(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().lower().startswith("select"):
            sql.append(statement)

    event.listen(engine, "before_cursor_execute", trace)
    try:
        result = _new(db, page=1, page_size=25)
    finally:
        event.remove(engine, "before_cursor_execute", trace)

    assert len(result["events"]) == 25
    assert len(sql) <= 12, f"N+1 query regression: {len(sql)}"
    text = "\n".join(sql).lower()
    assert " limit " in text
    assert " group by " in text


def test_519_invalid_filter_falls_back_to_all(timeline_db):
    db, _ = timeline_db
    actual = _new(db, event_type="unknown")
    standard = _new(db)
    assert actual["event_type"] == "all"
    assert actual["events"] == standard["events"]
