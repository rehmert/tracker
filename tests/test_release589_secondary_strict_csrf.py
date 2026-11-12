"""Release 589: independently signed secondary-account CSRF and isolation.

Tests run inside pytest's private workspace, not an installed account DB.
The secondary gateway has its own mandatory CSRF; global strict mode is not
a substitute for independent signed session protection.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from scripts.secondary_integration440_support import (
    browser, _counts, _hidden, _login, _post_form,
)


def test_589_secondary_account_signed_https_mutation_and_cross_user_isolation(
    browser, monkeypatch,
):
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "1")
    client, root = browser
    _login(client, 2)
    page = client.get("/secondary/inventory")
    assert page.status_code == 200
    token = _hidden(page.text, "csrf_token")
    before2 = _counts(root, 2)["compounds"]
    before3 = _counts(root, 3)["compounds"]
    route = "/secondary/inventory/compounds"
    fields = {"name": "QA-589-PRIVATE-ALPHA", "category": "peptide",
              "primary_unit": "mg", "notes": ""}
    denied = client.post(route, data={**fields, "csrf_token": "forged"},
                         follow_redirects=False)
    assert denied.status_code == 403
    crossed = client.post(
        route, data={**fields, "csrf_token": token},
        headers={"Sec-Fetch-Site": "cross-site"},
        follow_redirects=False,
    )
    assert crossed.status_code == 403
    assert _counts(root, 2)["compounds"] == before2
    assert _counts(root, 3)["compounds"] == before3

    _post_form(client, "/secondary/inventory", route, fields)
    assert _counts(root, 2)["compounds"] == before2 + 1
    assert _counts(root, 3)["compounds"] == before3
    assert "QA-589-PRIVATE-ALPHA" in client.get("/secondary/inventory").text

    _login(client, 3)
    other = client.get("/secondary/inventory")
    assert other.status_code == 200
    assert "QA-589-PRIVATE-ALPHA" not in other.text
    assert _counts(root, 2)["compounds"] == before2 + 1
    assert _counts(root, 3)["compounds"] == before3


def test_589_secondary_secure_cookie_not_sent_over_http(browser, monkeypatch):
    monkeypatch.setenv("TRACKER_CSRF_ENFORCE", "1")
    https_client, root = browser
    with TestClient(https_client.app, base_url="http://tracker.test") as http:
        login = http.get("/secondary/login")
        assert login.status_code == 200
        token = _hidden(login.text, "csrf_token")
        # The independently signed secondary CSRF cookie has Secure=True,
        # so even the matching form token cannot authenticate an HTTP write.
        response = http.post(
            "/secondary/login",
            data={"username": "member-2",
                  "password": "secondary-secure-password-2-440",
                  "csrf_token": token},
            follow_redirects=False,
        )
        assert response.status_code == 403
        assert _counts(root, 2)["compounds"] == 0
        assert _counts(root, 3)["compounds"] == 0
