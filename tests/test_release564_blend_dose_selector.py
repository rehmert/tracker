"""Release 564: existing waterfall output can be selected from Dose Log.

Blend stock must remain separate from ordinary Vial/DoseLog accounting.
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Blend, BlendComponent, BlendDose, Compound, DoseLog, Vial
from app.routers.blends import blend_remaining


def test_existing_waterfall_blend_can_be_selected_and_logged_from_doses_page():
    name = "Waterfall dose selector " + uuid4().hex[:10]
    with TestClient(app) as client:
        with SessionLocal() as db:
            compound = Compound(name="Waterfall selection " + uuid4().hex[:9], primary_unit="mg")
            db.add(compound)
            db.flush()
            source = Vial(
                compound_id=compound.id,
                content_value=10,
                content_unit="mg",
                volume_ml=0.5,
                status="finished",
            )
            db.add(source)
            db.flush()
            blend = Blend(
                label=name,
                final_volume_ml=0.5,
                diluent_ml=0,
                capacity_ml=3,
                status="in_use",
                notes="Waterfall: source vials #" + str(source.id),
            )
            db.add(blend)
            db.flush()
            db.add(BlendComponent(
                blend_id=blend.id,
                source_vial_id=source.id,
                compound_id=compound.id,
                transferred_base=10000,
                transferred_ml=0.5,
                target_dose_base=1000,
                target_unit="mg",
            ))
            db.commit()
            blend_id = blend.id
            source_id = source.id

        page = client.get("/doses")
        assert page.status_code == 200
        assert 'id="dose-blend-picker"' in page.text
        assert 'id="dose-blend-select"' in page.text
        assert f'<option value="{blend_id}">' in page.text
        assert name in page.text
        assert "0.5 mL remaining" in page.text
        assert "window.location.assign('/blends/'" in page.text

        detail = client.get(f"/blends/{blend_id}")
        assert detail.status_code == 200
        assert 'id="log-blend-draw"' in detail.text
        assert 'action="/blends/' + str(blend_id) + '/doses"' in detail.text

        response = client.post(
            f"/blends/{blend_id}/doses",
            data={"taken_at": "2026-11-11T10:10", "volume_ml": "0.1", "kind": "dose"},
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
        assert "err=" not in response.headers["location"]

        with SessionLocal() as db:
            recorded = db.get(Blend, blend_id)
            assert abs(blend_remaining(recorded) - 0.4) < 1e-8
            assert db.query(BlendDose).filter_by(blend_id=blend_id).count() == 1
            assert db.query(DoseLog).filter_by(vial_id=source_id).count() == 0
            assert db.get(Vial, source_id).status == "finished"


def test_finished_blend_not_offered_for_new_dose():
    name = "Finished blend selection " + uuid4().hex[:10]
    with TestClient(app) as client:
        with SessionLocal() as db:
            blend = Blend(label=name, final_volume_ml=0.2, status="finished")
            db.add(blend)
            db.commit()
        page = client.get("/doses")
        assert page.status_code == 200
        assert name not in page.text
