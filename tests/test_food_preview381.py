"""Release 381: per-100g search previews and missing nutrients."""

import json
import math

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import food_search380


def test_macro_preview_retains_zero_and_unknown():
    values = food_search380.macro_preview({
        "energy-kcal_100g": 110,
        "proteins_100g": "12.5",
        "carbohydrates_100g": 0,
        "fat_100g": None,
    })

    assert values == {
        "energy": 110,
        "proteins": 12.5,
        "carbohydrates": 0,
    }
    assert "fat" not in values


def test_macro_preview_rejects_invalid_numbers():
    assert food_search380.macro_preview({
        "energy-kcal_100g": -1,
        "proteins_100g": float("nan"),
        "carbohydrates_100g": "invalid",
        "fat_100g": True,
    }) == {}


def test_search_result_includes_coverage():
    result = food_search380.normalize_results({
        "products": [
            {
                "code": "1234567890123",
                "product_name": "Test Yogurt",
                "nutriments": {
                    "energy-kcal_100g": 120,
                    "proteins_100g": 13,
                },
            },
            {
                "code": "2345678901234",
                "product_name": "No Nutrition",
            },
        ]
    })

    assert len(result) == 2
    assert result[0]["nutrition_available"] is True
    assert result[0]["macro_100g"]["proteins"] == 13
    assert result[0]["nutrition_basis"] == "per 100 g"
    assert result[1]["nutrition_available"] is False
    assert result[1]["macro_100g"] == {}


def test_external_lookup_is_still_read_only(monkeypatch):
    calls = []

    def fake_fetch(url, kind, **kwargs):
        calls.append((url, kind))
        return {
            "products": [{
                "code": "1234567890123",
                "product_name": "Test Product",
                "nutriments": {
                    "energy-kcal_100g": 150,
                },
            }]
        }

    monkeypatch.setattr(
        food_search380,
        "fetch_json494",
        fake_fetch,
    )

    app = FastAPI()
    app.include_router(food_search380.router)

    with TestClient(app) as browser:
        result = browser.get(
            "/food/search-name?q=Test%20Product"
        )

    assert result.status_code == 200
    item = result.json()["products"][0]
    assert item["macro_100g"]["energy"] == 150
    assert item["nutrition_available"] is True

    assert len(calls) == 1
    assert calls[0][1] == "name-legacy"
    assert calls[0][0].startswith(
        "https://world.openfoodfacts.org/cgi/search.pl?"
    )
