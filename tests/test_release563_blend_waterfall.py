"""Release 563: verified plan recording, waterfall, and display-only precision."""
from uuid import uuid4

from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import Compound, Vial, Blend, BlendComponent
from app.services import vial_views
from app.units import _num
from app.blend_workflow563 import calculate_waterfall


def _dry_vials(prefix, counts=(10, 20), compound_count=2):
    with SessionLocal() as db:
        groups = [
            Compound(name=f"{prefix}-{i}-{uuid4().hex[:8]}", primary_unit="mg")
            for i in range(compound_count)
        ]
        db.add_all(groups)
        db.flush()
        vials = [
            Vial(compound_id=groups[i % compound_count].id,
                 content_value=amount, content_unit="mg", status="sealed")
            for i, amount in enumerate(counts)
        ]
        db.add_all(vials)
        db.commit()
        return [v.id for v in vials]


def _plan_form(ids, *, label="Release563 prepared"):
    return {
        "submission_token": str(uuid4()),
        "confirmed_actual": "yes",
        "label": label,
        "source_id": [str(v) for v in ids],
        "target_amount": ["1", "2"],
        "target_unit": ["mg", "mg"],
        "source_bac_ml": ["0.5", "0.5"],
        "planner_draw_ml": "0.2",
        "planner_capacity_ml": "3",
        "planner_max_destinations": "1",
        "planner_allocation": "equal",
    }


def test_plan_preview_read_only_and_confirmed_record_atomic():
    ids = _dry_vials("r563plan")
    with TestClient(app) as client:
        data = _plan_form(ids, label=f"Release563 planned-{uuid4().hex[:8]}")
        before = client.post("/blends/reconstitution-preview", data=data)
        assert before.status_code == 200, before.text
        with SessionLocal() as db:
            assert all(db.get(Vial, i).volume_ml is None for i in ids)

        missing = dict(data, confirmed_actual="", submission_token=str(uuid4()))
        rejected = client.post("/blends/record-plan", data=missing, follow_redirects=False)
        assert rejected.status_code == 303
        assert "err=" in rejected.headers["location"]

        result = client.post("/blends/record-plan", data=data, follow_redirects=False)
        assert result.status_code == 303, result.text
        assert "/blends/" in result.headers["location"]
        assert "err=" not in result.headers["location"]
        with SessionLocal() as db:
            blend = db.query(Blend).filter_by(label=data["label"]).one()
            assert abs(blend.final_volume_ml - 2) < 1e-8
            assert len(blend.components) == 2
            assert all(db.get(Vial, i).status == "finished" for i in ids)
            assert all(db.get(Vial, i).volume_ml == 1 for i in ids)
            assert all(vial_views(db, [db.get(Vial,i)])[i].remaining_base == 0 for i in ids)
        replay = client.post("/blends/record-plan", data=data, follow_redirects=False)
        assert replay.status_code == 303
        assert "err=" in replay.headers["location"]


def test_partial_planned_transfers_leave_correct_active_inventory():
    ids = _dry_vials("r563partial")
    data = _plan_form(ids, label=f"R563 partial-{uuid4().hex[:8]}")
    data["planner_capacity_ml"] = "0.6"
    with TestClient(app) as client:
        response = client.post("/blends/record-plan", data=data, follow_redirects=False)
        assert response.status_code == 303
        assert "err=" not in response.headers["location"]
    with SessionLocal() as db:
        assert all(db.get(Vial, i).status == "in_use" for i in ids)
        for ident, expected in zip(ids, [7000, 14000]):
            assert abs(vial_views(db, [db.get(Vial, ident)])[ident].remaining_base - expected) < 1e-6


def _waterfall_form(ids, label):
    return {
        "submission_token": str(uuid4()),
        "confirmed_actual": "yes",
        "label": label,
        "waterfall_source_id": [str(i) for i in ids],
        "waterfall_bac_ml": "0.5",
        "waterfall_capacity_ml": "3",
        "waterfall_target_amount": "1",
        "waterfall_target_unit": "mg",
    }


def test_waterfall_three_same_compound_preview_and_single_result_record():
    ids = _dry_vials("r563waterfall", counts=(5, 5, 5), compound_count=1)
    data = _waterfall_form(ids, f"Waterfall R563-{uuid4().hex[:8]}")
    with TestClient(app) as client:
        preview = client.post("/blends/waterfall/preview", data=data)
        assert preview.status_code == 200, preview.text
        assert "not recorded" in preview.text
        with SessionLocal() as db:
            assert all(db.get(Vial, vid).status == "sealed" for vid in ids)

        recorded = client.post("/blends/waterfall/record", data=data, follow_redirects=False)
        assert recorded.status_code == 303, recorded.text
        assert "err=" not in recorded.headers["location"]
        with SessionLocal() as db:
            blend = db.query(Blend).filter_by(label=data["label"]).one()
            assert abs(blend.final_volume_ml - 0.5) < 1e-8
            assert len(blend.components) == 3
            assert [c.source_vial_id for c in blend.components] == ids
            assert abs(sum(c.transferred_base for c in blend.components) - 15000) < 1e-6
            assert all(db.get(Vial, vid).status == "finished" for vid in ids)
            assert all(vial_views(db, [db.get(Vial, vid)])[vid].remaining_base == 0 for vid in ids)
            assert db.get(Vial, ids[0]).volume_ml == 0.5
            assert all(db.get(Vial, i).volume_ml is None for i in ids[1:])


def test_waterfall_rejects_mixed_liquid_duplicates_and_seven_sources():
    ids = _dry_vials("r563invalid", counts=(5, 5, 5, 5, 5, 5, 5), compound_count=1)
    with TestClient(app) as client:
        data = _waterfall_form(ids[:6], "R563 invalid preview")
        assert client.post("/blends/waterfall/preview", data=data).status_code == 200
        assert client.post("/blends/waterfall/preview", data=dict(data, waterfall_source_id=[str(i) for i in ids])).status_code == 422
        assert client.post("/blends/waterfall/preview", data=dict(data, waterfall_source_id=[str(ids[0])]*2)).status_code == 422
        assert client.post("/blends/waterfall/preview", data=dict(data, waterfall_bac_ml="9")).status_code == 422
        assert client.post("/blends/waterfall/record", data=dict(data, confirmed_actual=""), follow_redirects=False).headers["location"].find("err=") >= 0
        with SessionLocal() as db:
            assert all(db.get(Vial, vid).status == "sealed" for vid in ids)
    other = _dry_vials("r563different")
    with TestClient(app) as client:
        data = _waterfall_form([ids[0], other[1]], "R563 mixed")
        assert client.post("/blends/waterfall/preview", data=data).status_code == 422


def test_numeric_display_has_three_decimals_without_exponents():
    assert _num(1.234567) == "1.235"
    assert _num(0.00000001) == "<0.001"
    assert _num(-0.00000001) == ">-0.001"
    assert _num(1200000.12345) == "1,200,000.123"
    assert "e" not in _num(0.00000001).lower()
