"""Regression tests for single-vial dilution planning."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.reconstitution_math import calculate


def sample(**updates):
    data = {
        "kind": "single",
        "method": "optimize",
        "components": [
            {"name": "Example", "amount": "10", "unit": "mg"}
        ],
        "target_amount": "0.5",
        "target_unit": "mg",
        "basis": "0",
        "syringe_ml": "1",
        "vial_capacity_ml": "3",
        "preferred_units": "10",
        "graduation_units": "1",
        "volume_step_ml": "0.01",
    }

    data.update(updates)
    return data


def test_exact_divisibility():
    result = calculate(sample())

    assert result["method"] == "optimize"
    assert result["complete_draws"] == 20
    assert result["theoretical_leftover"] == 0

    assert result["recommended"][
        "draw_units"
    ] == pytest.approx(10)

    assert result["recommended"][
        "nominal_final_ml"
    ] == pytest.approx(2)

    assert result["recommended"]["matches_volume_step"]


def test_unavoidable_remainder():
    result = calculate(
        sample(target_amount="0.7")
    )

    assert result["complete_draws"] == 14
    assert result["theoretical_leftover"] == pytest.approx(.2)
    assert result["recommended"]["draw_units"] == pytest.approx(7)

    assert result["recommended"][
        "nominal_final_ml"
    ] == pytest.approx(1)

    assert result["recommended"][
        "theoretical_leftover_ml"
    ] == pytest.approx(.02)


def test_iu_dimension():
    result = calculate(sample(
        components=[
            {"name": "Example IU", "amount": 100, "unit": "IU"}
        ],
        target_amount=5,
        target_unit="IU",
    ))

    assert result["complete_draws"] == 20

    with pytest.raises(ValueError, match="compatible"):
        calculate(
            sample(target_unit="IU")
        )


def test_syringe_capacity_and_small_draws():
    result = calculate(
        sample(target_amount="0.1")
    )

    assert result["complete_draws"] == 100
    assert result["recommended"]["draw_units"] == pytest.approx(3)

    assert any(
        "below 5" in warning
        for warning in result["warnings"]
    )

    with pytest.raises(ValueError, match="No selected"):
        calculate(sample(
            target_amount="0.001",
            vial_capacity_ml="0.1",
        ))

    with pytest.raises(ValueError, match="capacity"):
        calculate(sample(
            preferred_units=50,
            syringe_ml="0.3",
        ))


def test_invalid_inputs():
    with pytest.raises(ValueError, match="single compound"):
        calculate(sample(kind="blend"))

    for value in ("nan", "0", "-1", "inf", "oops"):
        with pytest.raises(ValueError):
            calculate(
                sample(target_amount=value)
            )

    with pytest.raises(ValueError):
        calculate(sample(vial_capacity_ml=0))

    with pytest.raises(ValueError, match="entire vial"):
        calculate(sample(target_amount=11))


def test_http_preview_is_read_only():
    with TestClient(app) as client:
        response = client.post(
            "/reconstitution-calculator/preview",
            json=sample(),
        )

        assert response.status_code == 200
        assert response.json()["complete_draws"] == 20

        invalid = client.post(
            "/reconstitution-calculator/preview",
            json=sample(target_amount="oops"),
        )

        assert invalid.status_code == 422
        assert "error" in invalid.json()
