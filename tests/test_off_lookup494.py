"""Hotfix 494: bounded OFF transport and barcode behavior without network."""

import json
from urllib.error import HTTPError, URLError

import pytest
from fastapi import HTTPException

from app import off_lookup494 as off
from app.routers import food


class FakeResponse:
    def __init__(self, payload):
        self.raw = (
            payload if isinstance(payload, bytes)
            else json.dumps(payload).encode("utf-8")
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.raw[:size]


@pytest.fixture(autouse=True)
def clean_lookup():
    off.reset_for_tests494()
    yield
    off.reset_for_tests494()


def test_successful_repeated_barcode_request_uses_ttl_cache(monkeypatch):
    calls = []
    def fake(request, timeout):
        calls.append((request.full_url, timeout))
        return FakeResponse({"status": 1, "product": {"product_name": "Yogurt"}})

    monkeypatch.setattr(off, "urlopen", fake)
    url = "https://world.openfoodfacts.org/api/v2/product/1234567890123?fields=product_name"
    first = off.fetch_json494(url, "barcode", ttl=3600)
    second = off.fetch_json494(url, "barcode", ttl=3600)
    assert first == second
    assert len(calls) == 1
    assert calls[0][1] == 7


def test_temporary_503_retries_once_then_succeeds(monkeypatch):
    calls = []
    def fake(request, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise HTTPError(request.full_url, 503, "busy", {}, None)
        return FakeResponse({"status": 1})

    monkeypatch.setattr(off, "urlopen", fake)
    monkeypatch.setattr(off.time, "sleep", lambda _seconds: None)
    url = "https://world.openfoodfacts.org/api/v2/product/1234567890123"
    assert off.fetch_json494(url, "barcode", retry=True)["status"] == 1
    assert len(calls) == 2


def test_429_uses_retry_after_without_retry(monkeypatch):
    calls = []
    def fail(request, timeout):
        calls.append(1)
        raise HTTPError(
            request.full_url, 429, "too many requests",
            {"Retry-After": "55"}, None,
        )

    monkeypatch.setattr(off, "urlopen", fail)
    url = "https://world.openfoodfacts.org/api/v2/product/1234567890123"
    with pytest.raises(off.OFFFailure494) as caught:
        off.fetch_json494(url, "barcode")
    assert caught.value.reason == "rate_limited"
    assert caught.value.retry_after == 55
    assert len(calls) == 1

    with pytest.raises(off.OFFFailure494) as second:
        off.fetch_json494(url, "barcode")
    assert second.value.reason == "cooldown"
    assert len(calls) == 1


def test_network_failure_and_cooldown(monkeypatch):
    calls = []
    def fail(request, timeout):
        calls.append(1)
        raise URLError("test network timeout")

    monkeypatch.setattr(off, "urlopen", fail)
    monkeypatch.setattr(off.time, "sleep", lambda _seconds: None)
    url = "https://world.openfoodfacts.org/cgi/search.pl?q=yogurt"
    with pytest.raises(off.OFFFailure494) as first:
        off.fetch_json494(url, "name-legacy")
    assert first.value.reason == "unavailable"
    assert len(calls) == 2

    with pytest.raises(off.OFFFailure494) as second:
        off.fetch_json494(url, "name-legacy")
    assert second.value.reason == "cooldown"
    assert len(calls) == 2


def test_invalid_json_or_oversized_response_fails_closed(monkeypatch):
    monkeypatch.setattr(
        off, "urlopen", lambda request, timeout: FakeResponse(b"not JSON"),
    )
    url = "https://search.openfoodfacts.org/search?q=milk"
    with pytest.raises(off.OFFFailure494):
        off.fetch_json494(url, "name-modern", retry=False)

    off.reset_for_tests494()
    monkeypatch.setattr(
        off, "urlopen",
        lambda request, timeout: FakeResponse(b"x" * (off.MAX_RESPONSE + 1)),
    )
    with pytest.raises(off.OFFFailure494) as error:
        off.fetch_json494(url, "name-modern", retry=False)
    assert error.value.reason == "oversized"


def test_block_unapproved_hosts_and_schemes_without_network(monkeypatch):
    monkeypatch.setattr(
        off, "urlopen",
        lambda *args, **kwargs: pytest.fail("External request attempted"),
    )
    for url, kind in (
        ("http://world.openfoodfacts.org/cgi/search.pl", "name-legacy"),
        ("https://evil.example/cgi/search.pl", "name-legacy"),
        ("https://world.openfoodfacts.org/food", "name-legacy"),
        ("https://evil.example/api/v2/product/12345678", "barcode"),
        ("https://world.openfoodfacts.org/cgi/search.pl", "barcode"),
    ):
        with pytest.raises(ValueError):
            off.fetch_json494(url, kind)


def test_barcode_route_preserves_nutrition_and_units(monkeypatch):
    def fake(url, kind, **kwargs):
        assert kind == "barcode"
        return {
            "status": 1,
            "product": {
                "product_name": "Yogurt",
                "serving_size": "170 g",
                "nutriments": {
                    "energy-kcal_serving": 120,
                    "proteins_serving": 18,
                    "sodium_serving": 0.05,
                },
            },
        }

    monkeypatch.setattr(food, "fetch_json494", fake)
    result = food.barcode_lookup("1234567890123")
    assert result["name"] == "Yogurt"
    assert result["nutrients"]["energy"] == 120.0
    assert result["nutrients"]["proteins"] == 18.0
    assert result["nutrients"]["sodium"] == 50.0
    assert result["basis"] == "per stated serving"


def test_barcode_http_429_503_and_not_found(monkeypatch):
    for reason, expected in (
        ("rate_limited", 429), ("unavailable", 503),
        ("not_found", 404),
    ):
        def fail(url, kind, **kwargs):
            raise off.OFFFailure494(reason, retry_after=40)
        monkeypatch.setattr(food, "fetch_json494", fail)
        with pytest.raises(HTTPException) as result:
            food.barcode_lookup("1234567890123")
        assert result.value.status_code == expected


def test_barcode_200_status_zero_is_not_found(monkeypatch):
    monkeypatch.setattr(
        food, "fetch_json494",
        lambda url, kind, **kwargs: {"status": 0},
    )
    with pytest.raises(HTTPException) as result:
        food.barcode_lookup("1234567890123")
    assert result.value.status_code == 404
