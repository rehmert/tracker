"""Release 711: correct/delete real prepared-blend withdrawals on QA SQLite only."""
from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Blend, BlendDose, ChangeAudit, DoseLog, Supply, SupplyUsage
from app.blend_dose_unified710 import remaining_blend_ml710
from tests.test_release710_unified_blend_dose import _seed, _form


def _header(client):
    response = client.get("/doses")
    assert response.status_code == 200
    token = client.cookies.get("tracker_csrf_v1")
    assert token and token.startswith("v1.")
    return {"X-Tracker-CSRF": token}


def _create(client, bid, header, supply_id=None, *, volume="0.2", kind="dose"):
    payload = _form(bid, token=str(uuid4()), amount=volume, kind=kind)
    if supply_id is not None:
        payload["supply_id_used"] = str(supply_id)
        payload[f"supply_qty_{supply_id}"] = "2"
    result = client.post("/doses", data=payload, headers=header, follow_redirects=False)
    assert result.status_code in (200, 303), result.text
    with SessionLocal() as db:
        draws = list(db.scalars(select(BlendDose).where(BlendDose.blend_id == bid)))
        assert draws
        return draws[-1].id


def _edit(client, did, header, supply_id=None, *, amount="0.5", unit="mL",
          kind="waste", site="Quadriceps right", notes="Corrected QA711", **options):
    data = {
        "taken_at": "2026-11-19T13:05", "amount": amount, "unit": unit,
        "kind": kind, "site": site, "notes": notes,
    }
    if supply_id is not None:
        data["supply_id_used"] = str(supply_id)
        data[f"supply_qty_{supply_id}"] = "1"
    data.update(options)
    return client.post(
        f"/doses/blends/{did}/edit", data=data,
        headers=header, follow_redirects=False,
    )


def test_711_edit_physical_blend_adjusts_volume_supplies_audit_without_vial_rows():
    bid, _, source_ids, sid = _seed()
    with TestClient(app) as client:
        header = _header(client)
        did = _create(client, bid, header, sid)
        page = client.get(f"/doses/blends/{did}/edit")
        assert page.status_code == 200
        assert 'name="confirm_delete"' in page.text
        assert 'data-original="2.0"' in page.text or 'data-original="2"' in page.text
        assert 'name="unit"' in page.text
        assert 'value="mg"' not in page.text  # mixed blend: volume only
        result = _edit(client, did, header, sid)
        assert result.status_code == 303, result.text
        assert "/doses#dose-history-unified614" in result.headers["location"]
        with SessionLocal() as db:
            draw = db.get(BlendDose, did)
            assert draw.blend_id == bid
            assert draw.kind == "waste"
            assert draw.site == "Quadriceps right"
            assert draw.notes == "Corrected QA711"
            assert draw.taken_at == datetime(2026, 11, 19, 13, 5)
            assert abs(draw.volume_ml - .5) < 1e-9
            assert draw.entered_value == .5 and draw.entered_unit == "mL"
            assert abs(remaining_blend_ml710(draw.blend) - 1.5) < 1e-9
            assert db.get(Supply, sid).remaining_qty == 4
            usage = list(db.scalars(select(SupplyUsage).where(
                SupplyUsage.blend_dose_id == did,
            )))
            assert len(usage) == 1 and usage[0].amount == 1
            assert db.query(DoseLog).filter(DoseLog.vial_id.in_(source_ids)).count() == 0
            event = db.scalar(select(ChangeAudit).where(
                ChangeAudit.entity_type == "blend_dose",
                ChangeAudit.entity_id == did, ChangeAudit.action == "edit",
            ))
            assert event is not None
            before, after = json.loads(event.before_json), json.loads(event.after_json)
            assert before["blend_id"] == after["blend_id"] == bid
            assert before["volume_ml"] == .2 and after["volume_ml"] == .5
            assert before["supplies"] == {str(sid): 2.0}
            assert after["supplies"] == {str(sid): 1.0}
        revised = client.get(f"/doses/blends/{did}/edit")
        assert revised.status_code == 200
        assert "Change history" in revised.text
        assert "Corrected QA711" in revised.text
        assert "Withdrawn volume" in revised.text
        timeline = client.get("/doses")
        assert f'href="/doses/blends/{did}/edit"' in timeline.text
        assert "0.5 mL withdrawn" in timeline.text
        detail = client.get(f"/blends/{bid}")
        assert f'href="/doses/blends/{did}/edit"' in detail.text


def test_711_rejects_overdraw_wrong_kind_site_and_unavailable_supplies_atomically():
    bid, _, source_ids, sid = _seed()
    with TestClient(app) as client:
        header = _header(client)
        did = _create(client, bid, header, sid)
        scenarios = [
            (dict(amount="2.01"), "exceeds remaining"),
            (dict(amount="1", unit="mg"), "must be logged"),
            (dict(kind="invalid"), "valid administration"),
            (dict(site="Not a valid injection site"), "Unknown injection site"),
            ({f"supply_qty_{sid}": "100"}, "Selected supplies exceed"),
        ]
        for change, error in scenarios:
            response = _edit(client, did, header, sid, **change)
            assert response.status_code == 303
            from urllib.parse import parse_qs, urlsplit
            location = response.headers.get("location", "")
            actual_error = parse_qs(urlsplit(location).query).get("err", [""])[0]
            assert error.lower() in actual_error.lower(), actual_error
            with SessionLocal() as db:
                draw = db.get(BlendDose, did)
                assert draw.volume_ml == .2
                assert draw.kind == "dose"
                assert db.get(Supply, sid).remaining_qty == 3
                assert db.query(ChangeAudit).filter_by(
                    entity_type="blend_dose", entity_id=did,
                ).count() == 0
                assert db.query(DoseLog).filter(DoseLog.vial_id.in_(source_ids)).count() == 0


def test_711_finished_blend_reopens_when_corrected_and_delete_restores_all_usage():
    bid, _, source_ids, sid = _seed()
    with TestClient(app) as client:
        header = _header(client)
        did = _create(client, bid, header, sid, volume="2")
        with SessionLocal() as db:
            assert db.get(Blend, bid).status == "finished"
        result = _edit(client, did, header, sid, amount="1.25", kind="dose")
        assert result.status_code == 303
        with SessionLocal() as db:
            blend = db.get(Blend, bid)
            assert blend.status == "in_use"
            assert abs(remaining_blend_ml710(blend) - .75) < 1e-9
            assert db.get(Supply, sid).remaining_qty == 4
        unchecked = client.post(
            f"/doses/blends/{did}/delete", data={}, headers=header,
            follow_redirects=False,
        )
        assert unchecked.status_code == 303
        with SessionLocal() as db:
            assert db.get(BlendDose, did) is not None
        removed = client.post(
            f"/doses/blends/{did}/delete", data={"confirm_delete": "yes"},
            headers=header, follow_redirects=False,
        )
        assert removed.status_code == 303, removed.text
        with SessionLocal() as db:
            assert db.get(BlendDose, did) is None
            blend = db.get(Blend, bid)
            assert blend.status == "in_use"
            assert remaining_blend_ml710(blend) == 2
            assert db.get(Supply, sid).remaining_qty == 5
            assert not list(db.scalars(select(SupplyUsage).where(
                SupplyUsage.blend_dose_id == did,
            )))
            audits = list(db.scalars(select(ChangeAudit).where(
                ChangeAudit.entity_type == "blend_dose",
                ChangeAudit.entity_id == did,
            ).order_by(ChangeAudit.id)))
            assert [a.action for a in audits] == ["edit", "delete"]
            deleted = json.loads(audits[-1].before_json)
            assert deleted["volume_ml"] == 1.25
            assert deleted["supplies"] == {str(sid): 1.0}
            assert db.query(DoseLog).filter(DoseLog.vial_id.in_(source_ids)).count() == 0
        twice = client.post(
            f"/doses/blends/{did}/delete", data={"confirm_delete": "yes"},
            headers=header, follow_redirects=False,
        )
        assert twice.status_code == 404


def test_711_legacy_blend_draw_without_entered_unit_can_be_corrected():
    bid, _, _, _ = _seed()
    with SessionLocal() as db:
        old = BlendDose(
            blend_id=bid, taken_at=datetime(2026, 11, 16, 8, 0),
            volume_ml=.1, kind="dose", site="", notes="Original legacy draw",
        )
        db.add(old)
        db.commit()
        did = old.id
    with TestClient(app) as client:
        header = _header(client)
        page = client.get(f"/doses/blends/{did}/edit")
        assert page.status_code == 200
        assert 'name="amount"' in page.text
        assert 'value="0.1"' in page.text
        result = _edit(client, did, header, amount=".3", unit="mL")
        assert result.status_code == 303
    with SessionLocal() as db:
        draw = db.get(BlendDose, did)
        assert draw.volume_ml == .3
        event = db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_type == "blend_dose",
            ChangeAudit.entity_id == did,
            ChangeAudit.action == "edit",
        ))
        assert json.loads(event.before_json)["entered_value"] is None
        assert json.loads(event.before_json)["entered_unit"] is None


def test_711_single_compound_mass_correction_keeps_same_physical_blend():
    bid, _, source_ids, _ = _seed(compound_count=1)
    with TestClient(app) as client:
        header = _header(client)
        did = _create(client, bid, header)
        result = _edit(client, did, header, amount="1", unit="mg")
        assert result.status_code == 303
    with SessionLocal() as db:
        draw = db.get(BlendDose, did)
        assert draw.entered_value == 1 and draw.entered_unit == "mg"
        assert abs(draw.volume_ml - .2) < 1e-9
        assert db.query(DoseLog).filter(DoseLog.vial_id.in_(source_ids)).count() == 0
