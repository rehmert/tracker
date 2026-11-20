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
from datetime import date

from app.models import BlendComponent, Compound, Purchase, Vial


def _seed(compound_count=2):
    from app.db import engine, Base
    from app.migrations import migrate

    migrate(engine)
    Base.metadata.create_all(engine)
    unique = uuid4().hex[:12]
    with SessionLocal() as db:
        purchase = Purchase(vendor="QA711 " + unique, purchased_on=date(2026, 11, 20))
        db.add(purchase)
        db.flush()
        compounds, sources = [], []
        for n in range(compound_count):
            compound = Compound(name=f"QA711-{unique}-{n}", primary_unit="mg")
            db.add(compound)
            db.flush()
            vial = Vial(compound_id=compound.id, purchase_id=purchase.id,
                        content_value=10 * (n + 1), content_unit="mg",
                        volume_ml=1, status="finished")
            db.add(vial)
            db.flush()
            compounds.append(compound)
            sources.append(vial)
        blend = Blend(label="QA711 prepared " + unique, final_volume_ml=2,
                      diluent_ml=0, capacity_ml=3, status="in_use")
        db.add(blend)
        db.flush()
        for n, (compound, vial) in enumerate(zip(compounds, sources)):
            db.add(BlendComponent(
                blend_id=blend.id, source_vial_id=vial.id,
                compound_id=compound.id, transferred_base=10000 * (n + 1),
                transferred_ml=1, target_dose_base=1000 * (n + 1),
                target_unit="mg",
            ))
        item = Supply(purchase_id=purchase.id, name="QA711 syringe " + unique,
                      kind="pill", purchased_qty=5, remaining_qty=5,
                      unit_price_cents=0)
        db.add(item)
        db.commit()
        return blend.id, [c.id for c in compounds], [v.id for v in sources], item.id


def _form(blend_id, token=None, **changes):
    data = {
        "vial_id": f"blend:{blend_id}",
        "amount": "0.2", "unit": "mL", "kind": "dose",
        "taken_at": "2026-11-18T08:20",
        "site": "Abdomen lower right",
        "notes": "QA711 synthetic draw",
        "submission_token": token or str(uuid4()),
    }
    data.update(changes)
    return data


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
        draw = db.scalar(select(BlendDose).where(
            BlendDose.blend_id == bid,
        ).order_by(BlendDose.id.desc()).limit(1))
        assert draw is not None
        return draw.id


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
        assert result.headers["location"].endswith("#dose-history-unified614")
        assert "/doses?msg=" in result.headers["location"]
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
    with TestClient(app) as client:
        header = _header(client)
        # Use the unchanged legacy endpoint, which creates exactly the
        # historical NULL entered-unit/value record under a write lock.
        response = client.post(
            f"/blends/{bid}/doses",
            data={
                "submission_token": str(uuid4()),
                "taken_at": "2026-11-16T08:00",
                "volume_ml": "0.1", "kind": "dose",
                "notes": "Original legacy draw",
            },
            headers=header, follow_redirects=False,
        )
        assert response.status_code == 303
        with SessionLocal() as db:
            draw = db.scalar(select(BlendDose).where(
                BlendDose.blend_id == bid,
            ).order_by(BlendDose.id.desc()).limit(1))
            assert draw is not None
            assert draw.entered_value is None and draw.entered_unit is None
            did = draw.id
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


def test_711_two_draws_reserve_each_others_volume_and_corrections_reopen_stock():
    bid, _, source_ids, _ = _seed()
    with TestClient(app) as client:
        header = _header(client)
        first = _create(client, bid, header, volume="1.2")
        second = _create(client, bid, header, volume=".8")
        with SessionLocal() as db:
            assert db.get(Blend, bid).status == "finished"
        over = _edit(client, first, header, amount="1.3")
        assert over.status_code == 303
        with SessionLocal() as db:
            assert abs(db.get(BlendDose, first).volume_ml - 1.2) < 1e-9
            assert abs(db.get(BlendDose, second).volume_ml - .8) < 1e-9
        correction = _edit(client, second, header, amount=".5")
        assert correction.status_code == 303
        with SessionLocal() as db:
            blend = db.get(Blend, bid)
            assert blend.status == "in_use"
            assert abs(remaining_blend_ml710(blend) - .3) < 1e-9
        deletion = client.post(
            f"/doses/blends/{first}/delete",
            data={"confirm_delete": "yes"}, headers=header,
            follow_redirects=False,
        )
        assert deletion.status_code == 303
        with SessionLocal() as db:
            blend = db.get(Blend, bid)
            assert db.get(BlendDose, first) is None
            assert db.get(BlendDose, second) is not None
            assert abs(remaining_blend_ml710(blend) - 1.5) < 1e-9
            assert db.query(DoseLog).filter(DoseLog.vial_id.in_(source_ids)).count() == 0


def test_711_deleted_blend_draw_identity_is_never_reused_for_a_new_draw():
    # SQLite INTEGER PRIMARY KEY otherwise reuses the largest removed ID.
    # Audit events must always belong to the ORIGINAL physical withdrawal.
    bid, _, _, _ = _seed()
    with TestClient(app) as client:
        headers = _header(client)
        original_id = _create(client, bid, headers)
        corrected = _edit(client, original_id, headers, amount=".25")
        assert corrected.status_code == 303
        removed = client.post(
            f"/doses/blends/{original_id}/delete",
            data={"confirm_delete": "yes"},
            headers=headers, follow_redirects=False,
        )
        assert removed.status_code == 303
        new_id = _create(client, bid, headers, volume=".2")
        assert new_id > original_id
        legacy = client.post(
            f"/blends/{bid}/doses",
            data={"submission_token": str(uuid4()), "taken_at": "2026-11-20T11:00",
                  "volume_ml": ".2", "kind": "dose", "notes": "QA711 legacy flow"},
            headers=headers, follow_redirects=False,
        )
        assert legacy.status_code == 303
        with SessionLocal() as db:
            physical_ids = list(db.scalars(select(BlendDose.id).where(
                BlendDose.blend_id == bid,
            ).order_by(BlendDose.id)))
            assert len(physical_ids) == 2
            assert physical_ids[0] == new_id
            assert physical_ids[1] > new_id
            audit = list(db.scalars(select(ChangeAudit).where(
                ChangeAudit.entity_type == "blend_dose",
                ChangeAudit.entity_id == original_id,
            ).order_by(ChangeAudit.id)))
            assert [event.action for event in audit] == ["edit", "delete"]
            assert db.get(BlendDose, original_id) is None
