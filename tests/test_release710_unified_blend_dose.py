"""Release 710: one physical vial picker and dose workflow for Blend and Vial.

Only the disposable test database configured by the DEV qualification
wrapper is used. No real administration is inferred or recommended.
"""
from datetime import date
from uuid import uuid4
from urllib.parse import quote

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select

from app.blend_administration_view import blend_dose_components
from app.blend_dose_unified710 import (
    source_identity710, resolve_blend_draw710, remaining_blend_ml710,
)
from app.db import Base, SessionLocal, engine
from app.main import app
from app.migrations import migrate
from app.models import (
    Blend, BlendComponent, BlendDose, ChangeAudit, Compound, DoseLog,
    Purchase, Supply, SupplyUsage, Vial,
)


def _seed(compound_count=2):
    # Test fixtures can be seeded before TestClient starts the app.
    # Both schema setup and subsequent writes target disposable QA only.
    migrate(engine)
    Base.metadata.create_all(engine)
    unique = uuid4().hex[:12]
    with SessionLocal() as db:
        purchase = Purchase(vendor="QA710 " + unique, purchased_on=date(2026, 11, 15))
        db.add(purchase)
        db.flush()
        compounds, sources = [], []
        for n in range(compound_count):
            c = Compound(name=f"QA710-{unique}-{n}", primary_unit="mg")
            db.add(c)
            db.flush()
            v = Vial(compound_id=c.id, purchase_id=purchase.id,
                     content_value=10 * (n + 1), content_unit="mg",
                     volume_ml=1, status="finished")
            db.add(v)
            db.flush()
            compounds.append(c)
            sources.append(v)
        physical = Blend(
            label="Prepared #QA710 " + unique, final_volume_ml=2,
            diluent_ml=0, capacity_ml=3, status="in_use",
        )
        db.add(physical)
        db.flush()
        for n, (c, v) in enumerate(zip(compounds, sources)):
            db.add(BlendComponent(
                blend_id=physical.id, source_vial_id=v.id,
                compound_id=c.id, transferred_base=10000 * (n + 1),
                transferred_ml=1, target_dose_base=1000 * (n + 1),
                target_unit="mg",
            ))
        item = Supply(purchase_id=purchase.id, name="QA710 syringe " + unique,
                      kind="pill", purchased_qty=5, remaining_qty=5,
                      unit_price_cents=0)
        db.add(item)
        db.commit()
        return physical.id, [x.id for x in compounds], [v.id for v in sources], item.id


def _signed(client):
    response = client.get("/doses")
    assert response.status_code == 200
    token = client.cookies.get("tracker_csrf_v1")
    assert isinstance(token, str) and token.startswith("v1.")
    return {"X-Tracker-CSRF": token, "HX-Request": "true"}


def _form(blend_id, token=None, **changes):
    result = {
        "vial_id": f"blend:{blend_id}",
        "amount": "0.2", "unit": "mL", "kind": "dose",
        "taken_at": "2026-11-18T08:20",
        "site": "Abdomen lower right",
        "notes": "QA710 genuine synthetic dose",
        "submission_token": token or str(uuid4()),
    }
    result.update(changes)
    return result


def test_710_mixed_blend_one_native_form_signed_site_supplies_replay_history():
    bid, compound_ids, source_ids, supply_id = _seed()
    with TestClient(app) as client:
        header = _signed(client)
        page = client.get(f"/doses?source={quote(f'blend:{bid}')}")
        assert page.status_code == 200
        assert 'id="dose-blend-picker"' not in page.text
        assert page.text.count('hx-post="/doses"') == 1
        assert f'value="blend:{bid}"' in page.text
        assert f'value="blend:{bid}" data-source="blend"' in page.text
        assert f'value="blend:{bid}" data-source="blend" data-mixed="true"' in page.text
        assert f'href="/doses?source=blend:{bid}' not in page.text

        response = client.post("/doses/preview", data={
            "vial_id": f"blend:{bid}", "amount": "0.2", "unit": "mL",
        }, headers=header)
        assert response.status_code == 200
        assert "0.2 mL" in response.text
        assert "1 mg" in response.text and "2 mg" in response.text
        forbidden = client.post("/doses/preview", data={
            "vial_id": f"blend:{bid}", "amount": "1", "unit": "mg",
        }, headers=header)
        assert "must be logged by its actual" in forbidden.text

        with SessionLocal() as db:
            blend = db.get(Blend, bid)
            before_source_logs = db.query(DoseLog).filter(
                DoseLog.vial_id.in_(source_ids)).count()
            assert before_source_logs == 0
            assert db.get(Supply, supply_id).remaining_qty == 5
            assert remaining_blend_ml710(blend) == 2

        token = str(uuid4())
        form = _form(bid, token=token, supply_id_used=str(supply_id),
                     **{f"supply_qty_{supply_id}": "2"})
        accepted = client.post("/doses", data=form, headers=header,
                               follow_redirects=False)
        assert accepted.status_code == 200, accepted.text
        assert accepted.headers.get("hx-redirect") == "/doses#dose-history-unified614"
        with SessionLocal() as db:
            blend = db.get(Blend, bid)
            draws = db.scalars(select(BlendDose).where(BlendDose.blend_id == bid)).all()
            assert len(draws) == 1
            draw = draws[0]
            assert abs(draw.volume_ml - 0.2) < 1e-9
            assert draw.entered_value == 0.2 and draw.entered_unit == "mL"
            assert draw.site == "Abdomen lower right"
            assert draw.notes == form["notes"]
            assert db.query(DoseLog).filter(DoseLog.vial_id.in_(source_ids)).count() == 0
            assert db.get(Supply, supply_id).remaining_qty == 3
            usages = db.scalars(select(SupplyUsage).where(
                SupplyUsage.blend_dose_id == draw.id)).all()
            assert len(usages) == 1 and usages[0].amount == 2
            assert usages[0].dose_id is None and usages[0].vial_id is None
            parts = blend_dose_components(draw)
            assert len(parts) == 2
            assert {x["compound_id"] for x in parts} == set(compound_ids)
            assert sorted(x["amount"] for x in parts) == [1000, 2000]
            assert abs(remaining_blend_ml710(blend) - 1.8) < 1e-9
            assert db.scalar(select(ChangeAudit).where(
                ChangeAudit.entity_type == "blend",
                ChangeAudit.entity_id == bid,
                ChangeAudit.action == "draw")) is not None

        replay = client.post("/doses", data=form, headers=header)
        assert "already recorded" in replay.text
        error = client.post("/doses", data=_form(bid, amount="1.9"), headers=header)
        assert "exceeds remaining" in error.text
        wrong_plan = client.post(
            "/doses", data=_form(bid, planned_compound_id="999999"),
            headers=header,
        )
        assert "does not contain the planned compound" in wrong_plan.text
        with SessionLocal() as db:
            assert db.query(BlendDose).filter_by(blend_id=bid).count() == 1
            assert db.get(Supply, supply_id).remaining_qty == 3
        history = client.get("/doses")
        assert history.status_code == 200
        assert 'data-timeline-source="blend"' in history.text
        assert "Abdomen lower right" in history.text
        assert "0.2 mL withdrawn" in history.text


def test_710_same_compound_multiple_source_vials_mass_converts_one_draw():
    bid, compound_ids, source_ids, _ = _seed(compound_count=1)
    with SessionLocal() as db:
        blend = db.get(Blend, bid)
        source = Vial(compound_id=compound_ids[0], content_value=10,
                      content_unit="mg", volume_ml=1, status="finished")
        db.add(source)
        db.flush()
        db.add(BlendComponent(
            blend_id=bid, source_vial_id=source.id,
            compound_id=compound_ids[0], transferred_base=10000,
            transferred_ml=1, target_dose_base=1000, target_unit="mg",
        ))
        db.commit()
    with TestClient(app) as client:
        header = _signed(client)
        preview = client.post("/doses/preview", data={
            "vial_id": f"blend:{bid}", "amount": "1", "unit": "mg",
        }, headers=header)
        assert "0.1 mL" in preview.text
        accepted = client.post(
            "/doses", data=_form(bid, amount="1", unit="mg"),
            headers=header, follow_redirects=False,
        )
        assert accepted.status_code == 200
    with SessionLocal() as db:
        draw = db.scalar(select(BlendDose).where(BlendDose.blend_id == bid))
        assert draw is not None and abs(draw.volume_ml - 0.1) < 1e-9
        assert draw.entered_value == 1 and draw.entered_unit == "mg"
        parts = blend_dose_components(draw)
        assert len(parts) == 1 and abs(parts[0]["amount"] - 1000) < 1e-8
        assert not db.query(DoseLog).filter(DoseLog.vial_id.in_(source_ids)).count()


def test_710_full_remaining_blend_waste_closes_physical_container():
    bid, _, source_ids, _ = _seed()
    with TestClient(app) as client:
        header = _signed(client)
        accepted = client.post(
            "/doses", data=_form(bid, kind="waste", amount="0",
                                 use_remaining="yes"),
            headers=header,
        )
        assert accepted.status_code == 200
    with SessionLocal() as db:
        blend = db.get(Blend, bid)
        assert blend.status == "finished"
        assert remaining_blend_ml710(blend) == 0
        draw = db.scalar(select(BlendDose).where(BlendDose.blend_id == bid))
        assert draw is not None and draw.kind == "waste"
        assert draw.volume_ml == 2 and draw.entered_unit == "mL"
        assert db.query(DoseLog).filter(DoseLog.vial_id.in_(source_ids)).count() == 0


def test_710_strict_source_identity_fail_closed_for_ambiguous_input():
    for good, expected in (
        ("7", ("vial", 7)),
        ("blend:3", ("blend", 3)),
    ):
        assert source_identity710(good) == expected
    for wrong in ("", "0", "-1", "blend:", "blend:0", "blend:-1",
                  "blends:1", "mix:5", "1.0", "blend:1/2"):
        try:
            source_identity710(wrong)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Accepted invalid physical source {wrong!r}")


def test_710_additive_migration_of_historical_blend_draws_and_supply_usage():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as db:
        db.exec_driver_sql(
            "CREATE TABLE blend_doses (id INTEGER PRIMARY KEY, blend_id INTEGER, "
            "taken_at TEXT, volume_ml REAL, kind TEXT, notes TEXT)"
        )
        db.exec_driver_sql(
            "INSERT INTO blend_doses VALUES "
            "(5,8,'2026-11-01T10:00',0.2,'dose','legacy')"
        )
        db.exec_driver_sql(
            "CREATE TABLE supply_usages (id INTEGER PRIMARY KEY, "
            "supply_id INTEGER, vial_id INTEGER, dose_id INTEGER, amount REAL)"
        )
        db.exec_driver_sql(
            "INSERT INTO supply_usages VALUES (3,2,NULL,NULL,1)"
        )
    migrate(engine)
    migrate(engine)
    names = {column["name"] for column in inspect(engine).get_columns("blend_doses")}
    assert {"site", "entered_value", "entered_unit"} <= names
    supply = {column["name"] for column in inspect(engine).get_columns("supply_usages")}
    assert "blend_dose_id" in supply
    with engine.connect() as db:
        assert db.exec_driver_sql(
            "SELECT id,volume_ml,notes,site,entered_value,entered_unit "
            "FROM blend_doses"
        ).one() == (5, 0.2, "legacy", "", None, None)
        assert db.exec_driver_sql(
            "SELECT id,supply_id,amount,blend_dose_id FROM supply_usages"
        ).one() == (3, 2, 1, None)
    engine.dispose()
