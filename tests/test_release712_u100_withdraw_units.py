"""Release 712: U-100 syringe units are volume at physical vial withdrawal.

Runs against disposable QA SQLite only (TRACKER_DATA_DIR isolated by
scripts/tracker-qualify712.sh). No clinical dosing recommendations.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import units as U
from app.blend_dose_unified710 import resolve_blend_draw710, remaining_blend_ml710
from app.db import Base, SessionLocal, engine
from app.main import app
from app.migrations import migrate
from app.models import (
    Blend, BlendComponent, BlendDose, ChangeAudit, Compound,
    DoseLog, Purchase, Vial,
)

ROOT = Path(__file__).resolve().parents[1]


def seed(kind="mass", *, volume_ml=2.0, prepared=False):
    migrate(engine)
    Base.metadata.create_all(engine)
    tag = uuid4().hex[:10]
    with SessionLocal() as db:
        purchase = Purchase(vendor="QA712-" + tag, purchased_on=date(2026, 11, 20))
        db.add(purchase)
        db.flush()
        components = []
        for i in range(2 if prepared else 1):
            compound = Compound(name=f"QA712-{tag}-{i}", primary_unit="IU" if kind == "iu" else "mg")
            db.add(compound)
            db.flush()
            vial = Vial(
                compound_id=compound.id, purchase_id=purchase.id,
                content_value=(30 if kind == "iu" else 10 * (i + 1)),
                content_unit=("IU" if kind == "iu" else "mg"),
                volume_ml=volume_ml if not prepared else 1,
                status="finished" if prepared else "in_use",
            )
            db.add(vial)
            db.flush()
            components.append((compound.id, vial.id))
        blend_id = None
        if prepared:
            blend = Blend(
                label="QA712 prepared " + tag,
                final_volume_ml=2, diluent_ml=0, capacity_ml=3,
                status="in_use",
            )
            db.add(blend)
            db.flush()
            blend_id = blend.id
            for i, (compound_id, vid) in enumerate(components):
                db.add(BlendComponent(
                    blend_id=blend_id, source_vial_id=vid,
                    compound_id=compound_id,
                    transferred_base=10000 * (i + 1),
                    transferred_ml=1,
                    target_dose_base=1000 * (i + 1),
                    target_unit="mg",
                ))
        db.commit()
        return {
            "vial": components[0][1],
            "blend": blend_id,
            "source_ids": [c[1] for c in components],
        }


def signed(client):
    page = client.get("/doses")
    assert page.status_code == 200
    token = client.cookies.get("tracker_csrf_v1")
    assert token and token.startswith("v1.")
    return {"X-Tracker-CSRF": token}


def form(source_id, *, amount="20", unit="units"):
    return {
        "vial_id": source_id,
        "amount": amount,
        "unit": unit,
        "kind": "dose",
        "taken_at": "2026-11-20T10:00",
        "site": "Abdomen lower right",
        "notes": "QA712 only",
        "submission_token": str(uuid4()),
    }


def test_712_u100_units_are_volume_and_never_iu_potency():
    u = U.parse_unit("units")
    assert u.dim == "volume"
    assert u.name == "units"
    assert u.factor == pytest.approx(0.01)
    assert U.parse_unit("U-100 units") == u
    assert U.convert(20, "units", "mL") == pytest.approx(.2)
    assert U.convert(20, "units", "uL") == pytest.approx(200)
    assert U.ml_to_syringe_units(.2) == pytest.approx(20)
    assert U.amount_to_vial_base(20, "units", "mass", 5000) == pytest.approx(1000)
    assert U.amount_to_vial_base(20, "units", "iu", 10) == pytest.approx(2)
    assert U.parse_unit("IU").dim == "iu"
    with pytest.raises(U.UnitError):
        U.convert(1, "IU", "units")
    with pytest.raises(U.UnitError):
        U.convert(1, "units", "IU")
    with pytest.raises(U.UnitError):
        U.amount_to_vial_base(20, "units", "mass", None)
    assert "units" in U.WITHDRAW_UNITS
    assert "units" not in U.DOSE_UNITS
    assert "units" not in U.CONTENT_UNITS


def test_712_vial_preview_log_edit_repeat_and_inventory():
    seeded = seed()
    vial_id = seeded["vial"]
    with TestClient(app) as client:
        headers = signed(client)
        page = client.get("/doses")
        assert 'value="units"' in page.text
        assert "units (U-100 syringe)" in page.text
        assert "IU measures potency" in page.text
        preview = client.post(
            "/doses/preview",
            data={"vial_id": str(vial_id), "amount": "20", "unit": "units"},
            headers=headers,
        )
        assert preview.status_code == 200
        assert "0.2 mL" in preview.text
        assert "20 marks on a U-100 syringe" in preview.text
        assert "1,000 mcg" in preview.text
        recorded = client.post(
            "/doses", data=form(str(vial_id)), headers=headers,
            follow_redirects=False,
        )
        assert recorded.status_code in (200, 303), recorded.text
        with SessionLocal() as db:
            dose = db.scalar(select(DoseLog).where(DoseLog.vial_id == vial_id))
            assert dose is not None
            did = dose.id
            assert dose.entered_value == 20
            assert dose.entered_unit == "units"
            assert dose.amount_base == pytest.approx(1000)
        edit_page = client.get(f"/doses/{did}/edit")
        assert edit_page.status_code == 200
        assert '<option value="units" selected>' in edit_page.text
        edited = client.post(
            f"/doses/{did}/edit",
            data={
                "vial_id": str(vial_id), "taken_at": "2026-11-20T10:10",
                "amount": "25", "unit": "units",
                "kind": "dose", "site": "Abdomen lower right",
                "notes": "QA712 corrected",
            },
            headers=headers, follow_redirects=False,
        )
        assert edited.status_code == 303
        with SessionLocal() as db:
            dose = db.get(DoseLog, did)
            assert dose.entered_unit == "units"
            assert dose.entered_value == 25
            assert dose.amount_base == pytest.approx(1250)
            audits = list(db.scalars(select(ChangeAudit).where(
                ChangeAudit.entity_type == "dose",
                ChangeAudit.entity_id == did, ChangeAudit.action == "edit",
            )))
            assert len(audits) == 1
        repeat = client.get(f"/doses?repeat_from={did}")
        assert repeat.status_code == 200
        assert "Previous recorded details loaded for review only" in repeat.text
        assert '<option value="units" selected>' in repeat.text


def test_712_mixed_compound_blend_uses_units_without_double_deducting_sources():
    seeded = seed(prepared=True)
    bid = seeded["blend"]
    with TestClient(app) as client:
        headers = signed(client)
        page = client.get(f"/doses?source=blend:{bid}")
        assert page.status_code == 200
        assert f'value="blend:{bid}"' in page.text
        preview = client.post("/doses/preview", data={
            "vial_id": f"blend:{bid}", "amount": "20", "unit": "units",
        }, headers=headers)
        assert preview.status_code == 200
        assert "0.2 mL" in preview.text
        assert "1 mg" in preview.text
        assert "2 mg" in preview.text
        created = client.post("/doses",
                              data=form(f"blend:{bid}"), headers=headers,
                              follow_redirects=False)
        assert created.status_code == 303, created.text
        with SessionLocal() as db:
            draw = db.scalar(select(BlendDose).where(BlendDose.blend_id == bid))
            assert draw is not None
            did = draw.id
            assert draw.entered_value == 20
            assert draw.entered_unit == "units"
            assert draw.volume_ml == pytest.approx(.2)
            assert remaining_blend_ml710(draw.blend) == pytest.approx(1.8)
            assert db.query(DoseLog).filter(DoseLog.vial_id.in_(seeded["source_ids"])).count() == 0
        edit_page = client.get(f"/doses/blends/{did}/edit")
        assert edit_page.status_code == 200
        assert '<option value="units" selected>' in edit_page.text
        edited = client.post(f"/doses/blends/{did}/edit", data={
            "taken_at": "2026-11-20T10:15", "amount": "30",
            "unit": "units", "kind": "dose",
            "site": "Abdomen lower right", "notes": "QA712 corrected",
        }, headers=headers, follow_redirects=False)
        assert edited.status_code == 303, edited.text
        with SessionLocal() as db:
            draw = db.get(BlendDose, did)
            assert draw.entered_unit == "units"
            assert draw.entered_value == 30
            assert draw.volume_ml == pytest.approx(.3)
            assert remaining_blend_ml710(draw.blend) == pytest.approx(1.7)
            assert db.query(DoseLog).filter(DoseLog.vial_id.in_(seeded["source_ids"])).count() == 0
            assert db.scalar(select(ChangeAudit).where(
                ChangeAudit.entity_type == "blend_dose",
                ChangeAudit.entity_id == did, ChangeAudit.action == "edit",
            )) is not None


def test_712_iu_vial_syringe_units_represent_volume_not_iu():
    seeded = seed(kind="iu", volume_ml=3)
    vid = seeded["vial"]
    with TestClient(app) as client:
        headers = signed(client)
        preview = client.post("/doses/preview", data={
            "vial_id": str(vid), "amount": "20", "unit": "units",
        }, headers=headers)
        assert preview.status_code == 200
        assert "2 IU" in preview.text
        assert "0.2 mL" in preview.text
        saved = client.post("/doses", data=form(str(vid)), headers=headers)
        assert saved.status_code in (200, 303)
        with SessionLocal() as db:
            dose = db.scalar(select(DoseLog).where(DoseLog.vial_id == vid))
            assert dose is not None
            assert dose.amount_base == pytest.approx(2)
            assert dose.entered_value == 20
            assert dose.entered_unit == "units"


def test_712_no_known_liquid_volume_refuses_syringe_units():
    seeded = seed(volume_ml=None)
    vid = seeded["vial"]
    with TestClient(app) as client:
        headers = signed(client)
        preview = client.post("/doses/preview", data={
            "vial_id": str(vid), "amount": "20", "unit": "units",
        }, headers=headers)
        assert "known volume" in preview.text
        rejected = client.post("/doses", data=form(str(vid)), headers=headers)
        assert rejected.status_code != 303
        assert "known volume" in rejected.text
        with SessionLocal() as db:
            assert db.scalar(select(DoseLog).where(DoseLog.vial_id == vid)) is None


def test_712_overdraw_refused_atomically_for_syringe_units():
    seeded = seed(volume_ml=2)
    vid = seeded["vial"]
    with TestClient(app) as client:
        headers = signed(client)
        response = client.post("/doses", data=form(str(vid), amount="201"),
                               headers=headers)
        assert "exceeds remaining vial contents" in response.text
        with SessionLocal() as db:
            assert db.scalar(select(DoseLog).where(DoseLog.vial_id == vid)) is None


def test_712_protocol_dose_options_did_not_become_syringe_units():
    from app.templating import templates
    assert "units" not in templates.env.globals["DOSE_UNITS"]
    assert "units" in templates.env.globals["WITHDRAW_UNITS"]
    protocol = (ROOT / "app/templates/_protocol_row.html").read_text()
    assert "{% for u in DOSE_UNITS %}" in protocol
    assert "WITHDRAW_UNITS" not in protocol
    dose = (ROOT / "app/templates/doses.html").read_text()
    assert "WITHDRAW_UNITS" in dose
    assert "units (U-100 syringe)" in dose
    assert "U-100 syringe units" in dose


def test_712_client_source_switch_preserves_volume_units():
    source = (ROOT / "app/static/js/tracker-dose-source710.js").read_text()
    assert "['mL', 'uL', 'units'].includes(unit.value)" in source
    assert "amount.value = '';" in source
    assert "unit.value = 'mL';" in source
