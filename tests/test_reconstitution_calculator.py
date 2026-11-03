"""Read-only single-vial and shared-vial calculator tests."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.reconstitution_math import calculate
from app.db import SessionLocal
from app.models import Compound, Vial


def single(**changes):
    data = {
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
        "target_amount": 250,
        "target_unit": "mcg",
    }
    data.update(changes)
    return data


def blend(**changes):
    data = single(
        kind="blend",
        target_amount=1,
        target_unit="mg",
        components=[
            {
                "name": "A",
                "amount": 10,
                "unit": "mg",
            },
            {
                "name": "B",
                "amount": 20,
                "unit": "mg",
            },
        ],
    )
    data.update(changes)
    return data


def test_single_vial_and_units():
    result = calculate(single())

    assert result["final_volume_ml"] == 2
    assert result["draw_ml"] == pytest.approx(.05)
    assert result["draw_units"] == pytest.approx(5)
    assert result["full_draws"] == 40

    assert result["components"][0][
        "concentration"
    ] == 5

    assert result["components"][0][
        "per_mark"
    ] == pytest.approx(.05)


def test_blend_delivers_both_components():
    result = calculate(blend())

    assert result["draw_ml"] == pytest.approx(.2)
    assert [
        component["amount_per_draw"]
        for component in result["components"]
    ] == pytest.approx([1, 2])

    assert result["full_draws"] == 10


def test_total_blend_basis():
    result = calculate(
        blend(basis="total", target_amount=3)
    )

    assert result["draw_units"] == pytest.approx(20)


def test_reverse_solver():
    result = calculate(
        single(
            method="reverse",
            target_amount=500,
            draw_units=10,
        )
    )

    assert result["final_volume_ml"] == pytest.approx(2)
    assert result["draw_ml"] == pytest.approx(.1)


def test_draw_based_measurement():
    result = calculate(
        single(method="draw", draw_units=5)
    )

    assert result["components"][0][
        "amount_per_draw"
    ] == pytest.approx(.25)


def test_iu_is_distinct_from_syringe_marks():
    result = calculate(
        single(
            components=[
                {
                    "name": "IU example",
                    "amount": 100,
                    "unit": "IU",
                }
            ],
            target_amount=5,
            target_unit="IU",
        )
    )

    assert result["draw_units"] == pytest.approx(10)
    assert result["components"][0][
        "amount_per_draw"
    ] == pytest.approx(5)

    with pytest.raises(ValueError, match="does not match"):
        calculate(
            single(
                components=[
                    {"amount": 100, "unit": "IU"}
                ]
            )
        )


def test_invalid_mixed_blend_total_and_bad_numbers():
    with pytest.raises(ValueError, match="compatible"):
        calculate(
            blend(
                basis="total",
                components=[
                    {"amount": 10, "unit": "mg"},
                    {"amount": 20, "unit": "IU"},
                ],
            )
        )

    for value in ("0", "-1", "nan", "inf", "oops"):
        with pytest.raises(ValueError):
            calculate(single(volume_ml=value))

    with pytest.raises(ValueError, match="entire vial"):
        calculate(
            single(
                target_amount=11,
                target_unit="mg",
            )
        )


def test_fractional_mark_and_capacity_warnings():
    result = calculate(
        single(
            target_amount=1,
            target_unit="mg",
            syringe_ml=.3,
            volume_ml=10,
            vial_capacity_ml=3,
        )
    )

    assert not result["fits_syringe"]
    assert len(result["warnings"]) >= 2

    result = calculate(
        single(
            target_amount=12.5,
            target_unit="mcg",
        )
    )

    assert any(
        "whole-unit" in warning
        for warning in result["warnings"]
    )


def test_post_preview_is_read_only_and_validates_payload():
    with TestClient(app) as client:
        assert client.get(
            "/reconstitution-calculator"
        ).status_code == 200

        response = client.post(
            "/reconstitution-calculator/preview",
            json=single(),
        )

        assert response.status_code == 200
        assert response.json()[
            "draw_units"
        ] == pytest.approx(5)

        response = client.post(
            "/reconstitution-calculator/preview",
            json=single(volume_ml="nan"),
        )

        assert response.status_code == 422
        assert "error" in response.json()

        assert client.post(
            "/reconstitution-calculator/preview",
            json={},
        ).status_code == 422


def test_inventory_prefill_does_not_change_vial():
    with TestClient(app) as client:
        with SessionLocal() as db:
            compound = Compound(
                name="Prefill example",
                primary_unit="mg",
            )
            db.add(compound)
            db.flush()

            vial = Vial(
                compound_id=compound.id,
                content_value=12.5,
                content_unit="mg",
                status="sealed",
            )
            db.add(vial)
            db.commit()
            vial_id = vial.id

        page = client.get(
            f"/reconstitution-calculator?vial_id={vial_id}"
        )

        assert page.status_code == 200
        assert "Prefill example" in page.text

        with SessionLocal() as db:
            same = db.get(Vial, vial_id)
            assert same.content_value == 12.5
            assert same.volume_ml is None
            assert same.status == "sealed"
