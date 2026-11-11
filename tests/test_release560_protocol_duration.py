"""Release 560: protocol duration behavior and persistence."""
from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Protocol
from app.routers.protocols import _parse_protocol_dates


def test_dates_mode_preserves_existing_behavior():
    assert _parse_protocol_dates(
        "2026-11-16", "2027-02-07"
    ) == (
        date(2026, 11, 16),
        date(2027, 2, 7),
    )

    assert _parse_protocol_dates(
        "2026-11-16", ""
    ) == (date(2026, 11, 16), None)


def test_weeks_mode_calculates_inclusive_end():
    assert _parse_protocol_dates(
        "2026-11-16", "", "weeks", "12"
    ) == (
        date(2026, 11, 16),
        date(2027, 2, 7),
    )

    assert _parse_protocol_dates(
        "2028-02-26", "", "weeks", "1"
    ) == (
        date(2028, 2, 26),
        date(2028, 3, 3),
    )


@pytest.mark.parametrize("start,end,mode,weeks", [
    ("", "", "weeks", "4"),
    ("2026-11-16", "", "weeks", ""),
    ("2026-11-16", "", "weeks", "0"),
    ("2026-11-16", "", "weeks", "-1"),
    ("2026-11-16", "", "weeks", "4.5"),
    ("2026-11-16", "", "weeks", "521"),
    ("2026-11-16", "", "invalid", "4"),
    ("2026-02-30", "", "weeks", "4"),
    ("9999-12-31", "", "weeks", "4"),
    ("", "2026-12-01", "dates", ""),
    ("2026-12-01", "2026-11-01", "dates", ""),
])
def test_invalid_dates_are_rejected(start, end, mode, weeks):
    with pytest.raises(HTTPException) as exc:
        _parse_protocol_dates(start, end, mode, weeks)
    assert exc.value.status_code == 400


def test_editor_exposes_both_duration_modes():
    with TestClient(app, follow_redirects=False) as client:
        created = client.post(
            "/protocols",
            data={"name": "Duration UI " + uuid4().hex},
        )
        assert created.status_code == 303

        response = client.get(created.headers["location"])
        assert response.status_code == 200

        for token in (
            'name="start_date"',
            'name="end_date"',
            'name="duration_mode"',
            'name="duration_weeks"',
            'value="dates"',
            'value="weeks"',
            'name="horizon_weeks"',
        ):
            assert token in response.text


def test_save_add_and_dates_endpoint_persist_weeks():
    with TestClient(app, follow_redirects=False) as client:
        created = client.post(
            "/protocols",
            data={"name": "Duration persist " + uuid4().hex},
        )
        assert created.status_code == 303

        path = created.headers["location"].split("?")[0]
        pid = int(path.rsplit("/", 1)[-1])

        data = {
            "name": "Duration persistence",
            "start_date": "2026-11-16",
            "end_date": "2026-11-18",
            "duration_mode": "weeks",
            "duration_weeks": "12",
            "horizon_weeks": "6",
        }

        response = client.post(path + "/save", data=data)
        assert response.status_code == 303

        with SessionLocal() as db:
            p = db.get(Protocol, pid)
            assert p.start_date == date(2026, 11, 16)
            assert p.end_date == date(2027, 2, 7)
            assert p.horizon_weeks == 6

        response = client.post(
            path + "/add-item",
            data={**data, "duration_weeks": "4"},
        )
        assert response.status_code == 303

        with SessionLocal() as db:
            assert db.get(Protocol, pid).end_date == date(
                2026, 12, 13
            )

        response = client.post(
            path + "/dates",
            data={
                "start_date": "2026-11-16",
                "duration_mode": "weeks",
                "duration_weeks": "2",
            },
        )
        assert response.status_code == 303

        with SessionLocal() as db:
            assert db.get(Protocol, pid).end_date == date(
                2026, 11, 29
            )

        response = client.post(
            path + "/save",
            data={**data, "duration_weeks": "0"},
        )
        assert response.status_code == 400

        with SessionLocal() as db:
            assert db.get(Protocol, pid).end_date == date(
                2026, 11, 29
            )
