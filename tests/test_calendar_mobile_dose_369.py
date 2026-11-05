"""Calendar-to-dose regressions using isolated pytest SQLite data."""
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import DoseLog

from tests.test_calendar_auto_vial import (
    _seed, _url, _form_selection
)


def test_calendar_selects_recently_used_eligible_vial():
    compound, ids, other = _seed()

    with SessionLocal() as db:
        db.add(DoseLog(
            vial_id=ids[2],
            taken_at=datetime(2026,11,3,9),
            entered_value=1,
            entered_unit='mg',
            amount_base=1000,
            kind='dose'
        ))
        db.commit()

    with TestClient(app) as client:
        page=client.get(_url(compound))
        assert page.status_code==200
        assert _form_selection(page.text)==[str(ids[2])]
        assert 'Most recently logged eligible in-use vial preselected' in page.text

        select=re.search(
            r'<select name="vial_id" required>(.*?)</select>',
            page.text,re.S
        )
        assert select
        assert f'value="{other}"' not in select.group(1)
        assert 'name="planned_compound_id"' in page.text
        assert 'Confirm vial for ' in page.text
        assert 'tracker-calendar-dose-mobile369.css' in page.text

        assert f'value="{other}"' in client.get('/doses').text


def test_explicit_matching_vial_is_preserved():
    compound, ids, other = _seed()
    with TestClient(app) as client:
        page=client.get(_url(compound,f'&vial_id={ids[0]}'))
        assert _form_selection(page.text)==[str(ids[0])]

        different=client.get(_url(compound,f'&vial_id={other}'))
        assert _form_selection(different.text)==[str(ids[1])]


def test_calendar_submission_rejects_wrong_compound():
    compound, ids, other = _seed()

    with TestClient(app) as client:
        response=client.post('/doses',data={
            'vial_id':str(other),
            'planned_compound_id':str(compound),
            'taken_at':'2026-11-04T09:00',
            'amount':'1',
            'unit':'mg',
            'kind':'dose',
            'site':'',
            'submission_token':str(uuid4()),
        })

        assert response.status_code==200
        assert 'different compound than the calendar entry' in response.text
        assert 'HX-Trigger-After-Settle' not in response.headers

    with SessionLocal() as db:
        assert not db.query(DoseLog).filter(
            DoseLog.vial_id==other
        ).first()


def test_mobile_action_and_recording_contracts():
    root=Path(__file__).resolve().parents[1]
    calendar=(root/'app/templates/calendar.html').read_text()
    dose=(root/'app/templates/doses.html').read_text()
    css=(root/'app/static/css/tracker-calendar-dose-mobile369.css').read_text()

    assert 'Log this dose' in calendar
    assert 'Choose vial first' in calendar
    assert 'href="#calendar-vial-picker"' in dose
    assert 'hx-post="/doses"' in dose
    assert 'hx-target="#dose-body"' in dose
    assert 'tracker-dose-final-review.js' in dose
    assert '@media (max-width: 680px)' in css
    assert 'min-height: 54px' in css
