"""Release 611: blend draws appear in Calendar and Dose Log without double-counting.

Isolated test database is supplied by the repository test environment. These
tests do not write production data.
"""
from datetime import date, datetime
from uuid import uuid4
from urllib.parse import urlsplit, parse_qs

from fastapi.testclient import TestClient
from sqlalchemy import select, func

from app.main import app
from app.db import Base, SessionLocal, engine
from app.models import (
    Blend, BlendComponent, BlendDose, Compound, DoseLog, Protocol,
    ProtocolItem, Vial,
)
from app.blend_administration_view import blend_dose_components
from app.routers.calendar import _month_events, reconcile


def _seed():
    Base.metadata.create_all(bind=engine)
    unique = uuid4().hex[:12]
    today = date.today()
    with SessionLocal() as db:
        compounds = []
        vials = []
        for index in range(2):
            compound = Compound(name=f"QA611-{unique}-{index}", primary_unit="mg")
            db.add(compound)
            db.flush()
            vial = Vial(compound_id=compound.id, content_value=10,
                        content_unit="mg", volume_ml=1, status="sealed")
            db.add(vial)
            db.flush()
            compounds.append(compound)
            vials.append(vial)
        blend = Blend(label=f"QA611 blend {unique}", final_volume_ml=1.0,
                      diluent_ml=0, status="in_use")
        db.add(blend)
        db.flush()
        for index, (compound, vial) in enumerate(zip(compounds, vials)):
            db.add(BlendComponent(
                blend_id=blend.id, source_vial_id=vial.id,
                compound_id=compound.id, transferred_base=1000.0 * (index + 1),
                transferred_ml=0.1, target_dose_base=200.0 * (index + 1),
                target_unit="mcg",
            ))
        protocol = Protocol(name=f"QA611 plan {unique}", is_active=True,
                            start_date=today)
        db.add(protocol)
        db.flush()
        db.add(ProtocolItem(
            protocol_id=protocol.id, compound_id=compounds[0].id,
            position=0, amount_value=200, amount_unit="mcg",
            freq_count=1, freq_period="day", start_week=1,
            dose_days="", dose_time="10:30",
        ))
        db.commit()
        return blend.id, [c.id for c in compounds], today, blend.label


def test_611_blend_admin_visible_on_calendar_and_dose_log():
    blend_id, compound_ids, today, label = _seed()
    scheduled = today.isoformat()
    with TestClient(app) as client:
        # The calendar handoff passes its selected date/time to the blend form.
        handoff = client.get(
            f"/blends/{blend_id}?planned_date={scheduled}&planned_time=10:30"
        )
        assert handoff.status_code == 200
        assert f'name="taken_at" value="{scheduled}T10:30"' in handoff.text
        assert f'name="calendar_date" value="{scheduled}"' in handoff.text
        assert "Return to calendar" in handoff.text

        draw = client.post(
            f"/blends/{blend_id}/doses",
            data={
                "taken_at": f"{scheduled}T10:30", "volume_ml": "0.2",
                "kind": "dose", "calendar_date": scheduled,
                "submission_token": str(uuid4()),
            },
            follow_redirects=False,
        )
        assert draw.status_code == 303
        location = draw.headers["location"]
        assert urlsplit(location).path == "/calendar"
        assert parse_qs(urlsplit(location).query)["month"] == [scheduled[:7]]
        assert urlsplit(location).fragment == "calendar-day-" + scheduled

        calendar = client.get(f"/calendar?month={scheduled[:7]}")
        assert calendar.status_code == 200
        # The recorded first constituent matches a protocol item; the
        # second constituent is an unmatched actual administration.
        # Both must offer a direct link to the same physical source blend.
        assert calendar.text.count(f'href="/blends/{blend_id}"') >= 2
        assert f"View source blend #{blend_id}" in calendar.text

        history = client.get("/doses")
        assert history.status_code == 200
        assert f'href="/blends/{blend_id}"' in history.text
        assert label in history.text
        assert 'data-blend-dose-kind="dose"' in history.text
        # A blend record must not create a separate ordinary-vial administration.
        with SessionLocal() as db:
            draw_row = db.scalar(select(BlendDose).where(BlendDose.blend_id == blend_id))
            assert draw_row is not None
            assert len(blend_dose_components(draw_row)) == 2
            assert db.scalar(select(func.count()).select_from(DoseLog).where(
                DoseLog.vial_id.in_(select(Vial.id).where(
                    Vial.compound_id.in_(compound_ids)
                ))
            )) == 0
            first, end, events, _ = _month_events(today.replace(day=1), db)
            matched = events.get(today, [])
            assert any(
                e["status"] == "recorded" and e["compound_id"] == compound_ids[0]
                for e in matched
            )
            assert any(
                e["status"] == "extra" and e["compound_id"] == compound_ids[1]
                and f"blend #{blend_id}" in e["dose"]
                for e in matched
            )


def test_611_blend_waste_is_visible_in_history_but_not_calendar_admin():
    blend_id, compound_ids, today, label = _seed()
    with TestClient(app) as client:
        result = client.post(
            f"/blends/{blend_id}/doses",
            data={
                "taken_at": today.isoformat() + "T10:30",
                "volume_ml": "0.1", "kind": "waste",
                "submission_token": str(uuid4()),
            },
            follow_redirects=False,
        )
        assert result.status_code == 303
        assert urlsplit(result.headers["location"]).path == f"/blends/{blend_id}"
        history = client.get("/doses")
        assert 'data-blend-dose-kind="waste"' in history.text
        assert label in history.text
    with SessionLocal() as db:
        _, _, events, _ = _month_events(today.replace(day=1), db)
        assert not any(
            event["status"] == "recorded" and event["compound_id"] == compound_ids[0]
            for event in events.get(today, [])
        )
        assert not any(
            event["status"] == "extra" and event["compound_id"] in compound_ids
            for event in events.get(today, [])
        )


def test_613_reconcile_does_not_mislabel_ordinary_vial_dose_as_blend():
    planned = {date(2026, 11, 14): [
        {"compound_id": 11, "name": "Example", "dose": "1 mg"},
        {"compound_id": 12, "name": "Other", "dose": "2 mg"},
    ]}
    actual = {date(2026, 11, 14): [
        {"compound_id": 11, "name": "Example", "dose": "1 mg"},
        {"compound_id": 12, "name": "Other", "dose": "2 mg (blend #51)",
         "blend_id": 51},
        {"compound_id": 13, "name": "Extra", "dose": "0.5 mg (blend #51)",
         "blend_id": 51},
    ]}
    entries = reconcile(planned, actual, date(2026, 11, 15))[date(2026, 11, 14)]
    assert entries[0]["status"] == "recorded"
    assert entries[0]["actual_blend_id"] is None
    assert entries[1]["status"] == "recorded"
    assert entries[1]["actual_blend_id"] == 51
    assert entries[2]["status"] == "extra"
    assert entries[2]["blend_id"] == 51
