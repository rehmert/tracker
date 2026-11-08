"""Cross-origin write defense and legacy compatibility."""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.request_origin import (
    reject_cross_origin_write,
    same_origin_host,
)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "AUTH_USER", "")
    monkeypatch.setattr(config, "AUTH_PASS", "")

    with TestClient(app) as instance:
        yield instance


@pytest.mark.parametrize(
    "origin,host,expected",
    [
        ("http://testserver", "testserver", True),
        ("https://tracker.example", "tracker.example", True),
        ("https://tracker.example:8443",
         "tracker.example:8443", True),
        ("http://testserver:8000",
         "testserver:8000", True),
        ("https://tracker.example:8443",
         "tracker.example:443", False),
        ("https://attacker.example",
         "tracker.example", False),
        ("https://tracker.example.evil",
         "tracker.example", False),
        ("null", "tracker.example", False),
        ("https://tracker.example/path",
         "tracker.example", False),
        ("https://user@tracker.example",
         "tracker.example", False),
    ],
)
def test_host_comparison(origin, host, expected):
    assert same_origin_host(origin, host) is expected


def test_safe_methods_not_blocked_by_origin():
    headers = {
        "origin": "https://attacker.example",
        "host": "tracker.example",
        "sec-fetch-site": "cross-site",
    }

    for method in ("GET", "HEAD", "OPTIONS"):
        assert not reject_cross_origin_write(
            method, headers
        )


def test_missing_browser_headers_still_allowed():
    assert not reject_cross_origin_write(
        "POST",
        {"host": "testserver"},
    )


def test_cross_site_metadata_blocks_write():
    assert reject_cross_origin_write(
        "POST",
        {
            "host": "testserver",
            "sec-fetch-site": "cross-site",
        },
    )


def test_foreign_post_blocked_before_router(client):
    response = client.post(
        "/compounds",
        headers={
            "Origin": "https://attacker.example",
            "Sec-Fetch-Site": "cross-site",
        },
        data={"name": "Forbidden Origin Compound"},
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "same-origin"
    assert response.headers["cache-control"] == "private, no-store"

    listing = client.get("/compounds")
    assert listing.status_code == 200
    assert "Forbidden Origin Compound" not in listing.text


def test_foreign_origin_alone_blocks_post(client):
    response = client.post(
        "/compounds",
        headers={
            "Origin": "https://attacker.example",
        },
        data={"name": "Another Forbidden Compound"},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_null_origin_blocks_post(client):
    response = client.post(
        "/compounds",
        headers={"Origin": "null"},
        data={"name": "Null Origin Compound"},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_cross_site_fetch_metadata_alone_blocks_post(client):
    response = client.post(
        "/compounds",
        headers={"Sec-Fetch-Site": "cross-site"},
        data={"name": "Cross Site Compound"},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_same_origin_post_reaches_existing_validation(client):
    # No new records: missing required name, so existing
    # FastAPI form validation returns 422 after the guard.
    response = client.post(
        "/compounds",
        headers={
            "Origin": "http://testserver",
            "Sec-Fetch-Site": "same-origin",
        },
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 422


def test_legacy_post_without_origin_reaches_validation(client):
    response = client.post(
        "/compounds",
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 422


def test_get_with_foreign_origin_still_works(client):
    response = client.get(
        "/healthz",
        headers={
            "Origin": "https://attacker.example",
            "Sec-Fetch-Site": "cross-site",
        },
    )
    assert response.status_code == 200


def test_json_write_also_guarded(client):
    response = client.post(
        "/pk/compounds",
        headers={"Origin": "https://attacker.example"},
        json={"name": "Testosterone Cypionate"},
    )
    assert response.status_code == 403


def test_put_and_delete_blocked(client):
    for method in ("PUT", "DELETE", "PATCH"):
        assert reject_cross_origin_write(
            method,
            {
                "origin": "https://attacker.example",
                "host": "testserver",
            },
        )



@pytest.mark.parametrize(
    "method",
    ["POST", "PUT", "PATCH", "DELETE"],
)
def test_same_site_write_metadata_blocks(method):
    # A sibling subdomain is same-site but cross-origin.
    assert reject_cross_origin_write(
        method,
        {
            "host": "tracker.example",
            "sec-fetch-site": "same-site",
        },
    )


def test_same_site_header_cannot_be_overridden_by_origin():
    # Even if another header appears to match, retain the
    # conservative Fetch Metadata rejection.
    assert reject_cross_origin_write(
        "POST",
        {
            "host": "tracker.example",
            "origin": "https://tracker.example",
            "sec-fetch-site": "same-site",
        },
    )


def test_same_site_http_post_blocked_before_validation(client):
    response = client.post(
        "/compounds",
        headers={
            "Sec-Fetch-Site": "same-site",
        },
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "private, no-store"


def test_same_site_json_write_blocked(client):
    response = client.post(
        "/pk/compounds",
        headers={
            "Sec-Fetch-Site": "same-site",
        },
        json={"name": "Testosterone Cypionate"},
    )
    assert response.status_code == 403


def test_same_origin_metadata_allows_existing_validation(client):
    response = client.post(
        "/compounds",
        headers={
            "Origin": "http://testserver",
            "Sec-Fetch-Site": "same-origin",
        },
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 422


def test_user_initiated_metadata_keeps_legacy_behavior(client):
    # "none" is used for certain user-initiated browser
    # navigations. Its absence of an Origin is not proof
    # of a foreign write.
    response = client.post(
        "/compounds",
        headers={"Sec-Fetch-Site": "none"},
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 422


def test_foreign_origin_still_blocked_with_same_origin_metadata(client):
    response = client.post(
        "/compounds",
        headers={
            "Origin": "https://attacker.example",
            "Sec-Fetch-Site": "same-origin",
        },
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_safe_get_remains_unchanged(client):
    response = client.get(
        "/healthz",
        headers={"Sec-Fetch-Site": "same-site"},
    )
    assert response.status_code == 200
