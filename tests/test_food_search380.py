"""Release 380: external name search, bounded I/O and no writes."""

import json
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import food_search380


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return json.dumps(self.payload).encode("utf-8")


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(food_search380.router)

    with TestClient(app) as browser:
        yield browser


def test_search_name_and_normalization(client, monkeypatch):
    captured = []

    def fake_urlopen(request, timeout):
        captured.append((request.full_url, timeout))
        return FakeResponse({
            "products": [
                {
                    "code": "1234567890123",
                    "product_name": "Greek Yogurt",
                    "brands": "Example Brand",
                    "serving_size": "170 g",
                },
                {
                    "code": "1234567890123",
                    "product_name": "Duplicate",
                },
                {
                    "code": "not-a-barcode",
                    "product_name": "Invalid",
                },
                {
                    "code": "2345678901234",
                    "product_name": "",
                },
            ]
        })

    monkeypatch.setattr(
        food_search380, "urlopen", fake_urlopen
    )

    response = client.get(
        "/food/search-name?q=Greek%20Yogurt"
    )

    assert response.status_code == 200
    products = response.json()["products"]

    assert len(products) == 1
    assert products[0]["name"] == "Greek Yogurt"
    assert products[0]["serving"] == "170 g"

    url, timeout = captured[0]
    parsed = urlsplit(url)
    parameters = parse_qs(parsed.query)

    assert parsed.hostname == "world.openfoodfacts.org"
    assert parameters["search_terms"] == ["Greek Yogurt"]
    assert parameters["page_size"] == ["15"]
    assert parameters["json"] == ["1"]
    assert timeout == 8


def test_reject_short_or_oversized_queries(client):
    for query in ("", "a", "x" * 81):
        result = client.get(
            "/food/search-name",
            params={"q": query},
        )
        assert result.status_code == 422


def test_upstream_failure_is_recoverable(client, monkeypatch):
    def fail(request, timeout):
        raise URLError("unavailable")

    monkeypatch.setattr(
        food_search380, "urlopen", fail
    )

    result = client.get(
        "/food/search-name?q=chicken"
    )

    assert result.status_code == 503
    assert "unavailable" in result.json()["detail"]


def test_search_results_do_not_create_food_entries(
    client, monkeypatch
):
    monkeypatch.setattr(
        food_search380,
        "urlopen",
        lambda request, timeout: FakeResponse({
            "products": [
                {
                    "code": "1234567890123",
                    "product_name": "Test Yogurt",
                }
            ]
        }),
    )

    result = client.get("/food/search-name?q=yogurt")
    assert result.status_code == 200
    assert result.json()["products"][0]["name"] == "Test Yogurt"

    # There is no POST endpoint in the search router.
    assert client.post(
        "/food/search-name",
        json={"q": "yogurt"},
    ).status_code == 405
