"""Regression tests for read-only vial selection and calculator UX."""

import json
import re

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Coa, Compound, Vial
from app.reconstitution_math import calculate


def _prefill(page):
    match = re.search(
        r'<script id="recon-prefill" type="application/json">\s*(.*?)\s*</script>',
        page,
        flags=re.S,
    )
    assert match
    return json.loads(match.group(1))


def test_vial_picker_and_label_prefill_are_read_only():
    with TestClient(app) as client:
        with SessionLocal() as db:
            compound = Compound(
                name="Recon Workflow Label",
                primary_unit="mg",
            )
            db.add(compound)
            db.flush()

            vial = Vial(
                compound_id=compound.id,
                content_value=8,
                content_unit="mg",
                status="sealed",
            )
            db.add(vial)
            db.commit()
            vid = vial.id

        page = client.get("/reconstitution-calculator").text
        assert "Load a recent active vial from Tracker" in page
        assert "Recon Workflow Label" in page

        page = client.get(
            f"/reconstitution-calculator?vial_id={vid}"
        ).text

        initial = _prefill(page)

        assert initial["amount"] == pytest.approx(8)
        assert initial["content_source"] == "label"
        assert initial["remaining_amount"] == pytest.approx(8)
        assert initial["partial"] is False

        with SessionLocal() as db:
            saved = db.get(Vial, vid)
            assert saved.status == "sealed"
            assert saved.volume_ml is None


def test_coa_adjusted_prefill_is_explicit_and_not_saved():
    with TestClient(app) as client:
        with SessionLocal() as db:
            compound = Compound(
                name="Recon Workflow COA",
                primary_unit="mg",
            )

            coa = Coa(
                reported_content_value=12,
                reported_content_unit="mg",
            )

            db.add_all([compound, coa])
            db.flush()

            vial = Vial(
                compound_id=compound.id,
                content_value=10,
                content_unit="mg",
                status="sealed",
                use_coa_content=True,
                coa_id=coa.id,
            )

            db.add(vial)
            db.commit()
            vid = vial.id

        response = client.get(
            f"/reconstitution-calculator?vial_id={vid}"
        )

        assert response.status_code == 200
        initial = _prefill(response.text)

        assert initial["content_source"] == "COA average"
        assert initial["label_amount"] == pytest.approx(10)
        assert initial["amount"] == pytest.approx(12)
        assert initial["remaining_amount"] == pytest.approx(12)

        with SessionLocal() as db:
            saved = db.get(Vial, vid)
            assert saved.content_value == 10
            assert saved.use_coa_content is True


def test_only_active_vials_offered_in_picker():
    with TestClient(app) as client:
        with SessionLocal() as db:
            compound = Compound(
                name="Recon Finished Only",
                primary_unit="mg",
            )
            db.add(compound)
            db.flush()

            vial = Vial(
                compound_id=compound.id,
                content_value=5,
                content_unit="mg",
                status="finished",
            )
            db.add(vial)
            db.commit()
            vid = vial.id

        page = client.get("/reconstitution-calculator").text
        assert "Recon Finished Only" not in page

        historical = client.get(
            f"/reconstitution-calculator?vial_id={vid}"
        )

        assert historical.status_code == 200
        assert "Historical vial status" in historical.text


def test_workflow_controls_and_math_still_available():
    with TestClient(app) as client:
        page = client.get("/reconstitution-calculator").text

        assert 'id="recon-export"' in page
        assert 'id="recon-unit-hint"' in page
        assert 'id="recon-working-list"' in page
        assert "Understanding reconstitution calculations" in page

        result = client.post(
            "/reconstitution-calculator/preview",
            json={
                "kind": "single",
                "method": "target",
                "components": [
                    {
                        "name": "Example",
                        "amount": 10,
                        "unit": "mg",
                    }
                ],
                "volume_ml": 2,
                "syringe_ml": 1,
                "basis": "0",
                "target_amount": .5,
                "target_unit": "mg",
            },
        )

        assert result.status_code == 200
        assert result.json()["draw_units"] == pytest.approx(10)

        assert client.get(
            "/reconstitution-calculator?vial_id=999999999"
        ).status_code == 404


def test_optimizer_original_calculation_unchanged():
    result = calculate({
        "kind": "single",
        "method": "optimize",
        "components": [
            {"name": "A", "amount": 10, "unit": "mg"}
        ],
        "target_amount": .7,
        "target_unit": "mg",
        "syringe_ml": 1,
        "preferred_units": 10,
        "graduation_units": 1,
        "volume_step_ml": .01,
        "vial_capacity_ml": 3,
    })

    assert result["complete_draws"] == 14
    assert result["theoretical_leftover"] == pytest.approx(.2)
