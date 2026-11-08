"""Hotfix 494: name search, fallback, errors and no food writes.

Network interactions are fully mocked: tests never call Open Food Facts.
"""

from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.off_lookup494 import OFFFailure494
from app.routers import food_search380


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(food_search380.router)
    with TestClient(app) as browser:
        yield browser


def test_search_name_and_normalization(client, monkeypatch):
    captured = []

    def fake_fetch(url, kind, *, timeout, ttl, retry):
        captured.append((url, kind, timeout, ttl, retry))
        return {
            "products": [
                {
                    "code": "1234567890123", "product_name": "Greek Yogurt",
                    "brands": "Example Brand", "serving_size": "170 g",
                },
                {"code": "1234567890123", "product_name": "Duplicate"},
                {"code": "not-a-barcode", "product_name": "Invalid"},
                {"code": "2345678901234", "product_name": ""},
            ]
        }

    monkeypatch.setattr(food_search380, "fetch_json494", fake_fetch)
    result = client.get("/food/search-name?q=Greek%20Yogurt")

    assert result.status_code == 200
    products = result.json()["products"]
    assert len(products) == 1
    assert products[0]["name"] == "Greek Yogurt"
    assert products[0]["serving"] == "170 g"

    url, kind, timeout, ttl, retry = captured[0]
    assert kind == "name-legacy"
    assert urlsplit(url).hostname == "world.openfoodfacts.org"
    parameters = parse_qs(urlsplit(url).query)
    assert parameters["search_terms"] == ["Greek Yogurt"]
    assert parameters["page_size"] == ["15"]
    assert parameters["json"] == ["1"]
    assert timeout == 7
    assert retry is False


def test_reject_short_or_oversized_queries(client):
    for query in ("", "a", "x" * 81):
        result = client.get("/food/search-name", params={"q": query})
        assert result.status_code == 422


def test_upstream_503_triggers_modern_fallback(client, monkeypatch):
    calls = []

    def fake_fetch(url, kind, *, timeout, ttl, retry):
        calls.append((kind, url))
        if kind == "name-legacy":
            raise OFFFailure494("upstream_http", status=503)
        assert kind == "name-modern"
        return {
            "hits": [
                {"code": "1234567890123", "product_name": "Greek Yogurt"},
                {"_source": {"code": "2345678901234", "product_name": "Milk"}},
            ],
        }

    monkeypatch.setattr(food_search380, "fetch_json494", fake_fetch)
    response = client.get("/food/search-name?q=greek+yogurt")

    assert response.status_code == 200
    assert [p["name"] for p in response.json()["products"]] == [
        "Greek Yogurt", "Milk",
    ]
    assert [k for k, _ in calls] == ["name-legacy", "name-modern"]
    assert urlsplit(calls[1][1]).hostname == "search.openfoodfacts.org"


def test_search_both_upstreams_fail_returns_503(client, monkeypatch):
    def fail(url, kind, **kwargs):
        raise OFFFailure494("unavailable")

    monkeypatch.setattr(food_search380, "fetch_json494", fail)
    result = client.get("/food/search-name?q=chicken")
    assert result.status_code == 503
    assert "temporarily unavailable" in result.json()["detail"]


def test_search_both_rate_limited_returns_429(client, monkeypatch):
    def limited(url, kind, **kwargs):
        raise OFFFailure494("rate_limited", status=429, retry_after=35)

    monkeypatch.setattr(food_search380, "fetch_json494", limited)
    response = client.get("/food/search-name?q=chicken")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "35"


def test_malformed_modern_response_does_not_succeed(client, monkeypatch):
    def fake(url, kind, **kwargs):
        if kind == "name-legacy":
            raise OFFFailure494("unavailable")
        return {"wrong": "schema"}

    monkeypatch.setattr(food_search380, "fetch_json494", fake)
    response = client.get("/food/search-name?q=chicken")
    assert response.status_code == 503


def test_search_results_do_not_create_food_entries(client, monkeypatch):
    monkeypatch.setattr(
        food_search380,
        "fetch_json494",
        lambda url, kind, **kwargs: {
            "products": [
                {"code": "1234567890123", "product_name": "Test Yogurt"}
            ]
        },
    )
    result = client.get("/food/search-name?q=yogurt")
    assert result.status_code == 200
    assert result.json()["products"][0]["name"] == "Test Yogurt"
    assert client.post(
        "/food/search-name", json={"q": "yogurt"},
    ).status_code == 405
