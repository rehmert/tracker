"""Release 746: native signed Water MACD under opt-in strict CSRF.

Runs against disposable TestClient only. This is NOT a claim that every
unsafe Tracker route has the required signed HTTP+HTTPS positive coverage.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.csrf_runtime import COOKIE_NAME


@pytest.fixture
def strict(monkeypatch, tmp_path):
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE","1")
    monkeypatch.setattr(config,"AUTH_USER","")
    monkeypatch.setattr(config,"AUTH_PASS","")
    monkeypatch.setattr(config,"DATA_DIR",tmp_path)
    yield


@pytest.mark.parametrize("scheme",("http","https"))
def test_746_water_native_form_signed_edit_and_missing_or_forged_csrf(strict,scheme):
    with TestClient(app,base_url=f"{scheme}://testserver") as client:
        day="2026-11-08"
        resp=client.get("/food?day="+day)
        assert resp.status_code==200
        token=resp.cookies.get(COOKIE_NAME) or client.cookies.get(COOKIE_NAME)
        assert token
        missing=client.post("/food/water",data={"day":day,"ounces":"15"},
                            follow_redirects=False)
        assert missing.status_code==403
        valid=client.post("/food/water",data={
            "day":day,"ounces":"15","csrf_token":token
        },follow_redirects=False)
        assert valid.status_code==303
        page=client.get("/food?day="+day)
        assert page.status_code==200
        match=re.search(r'action="/food/water/(\d+)/edit"',page.text)
        assert match, "Native edit form absent after signed add"
        route=f"/food/water/{match.group(1)}/edit"
        untrusted=client.post(route,data={
            "original_day":day,"day":day,"ounces":"24",
        },follow_redirects=False)
        assert untrusted.status_code==403
        forged=client.post(route,data={
            "original_day":day,"day":day,"ounces":"24",
            "csrf_token":"forged-746",
        },follow_redirects=False)
        assert forged.status_code==403
        good=client.post(route,data={
            "original_day":day,"day":day,"ounces":"24",
            "csrf_token":token,
        },follow_redirects=False)
        assert good.status_code==303
        page=client.get("/food?day="+day)
        assert "24.0 fl oz" in page.text


def test_746_report_only_is_still_deployed_default(strict,monkeypatch):
    from app.csrf_enforcement520 import strict_csrf_enabled520
    from app.csrf_policy289 import reject_write
    assert strict_csrf_enabled520() is True
    assert reject_write("POST","missing","1") is True
    monkeypatch.delenv("TRACKER_CSRF_ENFORCE")
    assert strict_csrf_enabled520() is False
    assert reject_write("POST","missing","0") is False
