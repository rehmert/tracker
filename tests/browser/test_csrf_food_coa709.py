"""Release 709: the ten non-Workout post-627 strict-CSRF positive writes.

Private browser fixture only. Real Chrome renders the cookie-bound token;
tokenless/forged same-payload requests must be 403 with unchanged SQLite.
Valid requests must persist the intended food or COA state. Both localhost
HTTP and HTTPS are exercised.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import sync_playwright

HTTP_URL = os.environ.get("TRACKER_TEST_URL", "").rstrip("/")
HTTPS_URL = os.environ.get("TRACKER_TEST_HTTPS_URL", "").rstrip("/")
DATA = Path(os.environ.get("TRACKER_BROWSER_QA_DATA_DIR", "/")).resolve()
HTTP, HTTPS = urlsplit(HTTP_URL), urlsplit(HTTPS_URL)
if not (
    os.environ.get("TRACKER_TEST_ISOLATED") == "1"
    and os.environ.get("TRACKER_TEST_STRICT_CSRF") == "1"
    and HTTP.scheme == "http" and HTTPS.scheme == "https"
    and HTTP.hostname == HTTPS.hostname == "127.0.0.1"
    and HTTP.port not in (None, 8000)
    and HTTPS.port not in (None, 443, 8000, HTTP.port)
    and DATA.name == "data" and DATA.is_dir() and not DATA.is_symlink()
    and DATA.parent.parent == Path("/tmp").resolve()
    and re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
):
    raise RuntimeError("709 positive coverage must use private strict Chromium QA")
DB = DATA / "tracker.db"
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
FOOD_ROUTES = frozenset({
    ("POST", "/food/duplicates/merge"),
    ("POST", "/food/duplicates/resolve-unused"),
    ("POST", "/food/duplicates/keep-distinct"),
    ("POST", "/food/saved/{product_id}/edit"),
})
COA_ROUTES = frozenset({
    ("POST", "/coas/{cid}/attachments"),
    ("POST", "/coas/{cid}/attachments/{aid}/delete"),
    ("POST", "/coas/{cid}/attachments/{aid}/test-type"),
    ("POST", "/coas/{cid}/default-file"),
    ("POST", "/coas/{cid}/attachments/test-types"),
    ("POST", "/coas/{cid}/attachments/identifiers"),
})
ROUTES = FOOD_ROUTES | COA_ROUTES
assert len(ROUTES) == 10

NUTRIENTS = (
    "energy", "proteins", "carbohydrates", "fat", "fiber",
    "sugars", "saturated-fat", "sodium", "potassium", "calcium",
    "iron", "magnesium", "vitamin-c", "vitamin-d", "vitamin-b12", "cholesterol",
)


def read(sql, params=()):
    if not DB.is_file() or DB.is_symlink() or DB.resolve().parent != DATA:
        raise AssertionError("Invalid private SQLite database")
    with sqlite3.connect(DB, timeout=20) as connection:
        return connection.execute(sql, params).fetchone()


def seed_food(name, nutrient, *, barcode=""):
    # Only the browser server's configured private SQLite file is writable.
    assert DB.is_file() and not DB.is_symlink() and DB.resolve().parent == DATA
    with sqlite3.connect(DB, timeout=20) as connection:
        cursor = connection.execute(
            "INSERT INTO tracker_food_products "
            "(name,barcode,serving_description,nutrients,source) "
            "VALUES (?,?,?,?,?)",
            (name, barcode or None, "170 g", json.dumps(nutrient), "manual"),
        )
        return cursor.lastrowid


def token_context(browser, base, landing):
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    response = page.goto(base + landing, wait_until="networkidle")
    assert response is not None and response.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert isinstance(token, str) and token.startswith("v1.")
    cookie = next((c for c in context.cookies()
                   if c["name"] == "tracker_csrf_v1"), None)
    assert cookie is not None and cookie["value"] == token
    return context, page, token


def request(page, base, path, payload, csrf, *, multipart=False, want_json=False):
    args = {"max_redirects": 0}
    if multipart:
        args["multipart"] = payload
    else:
        args["form"] = payload
    headers = {}
    if csrf is not None:
        headers["X-Tracker-CSRF"] = csrf
    if want_json:
        headers["Accept"] = "application/json"
    if headers:
        args["headers"] = headers
    return page.request.post(base + path, **args)


def signed(page, base, path, payload, token, unchanged, *,
           status=303, multipart=False, want_json=False):
    original = unchanged()
    missing = request(page, base, path, payload, None,
                      multipart=multipart, want_json=want_json)
    assert missing.status == 403, (path, "missing", missing.status)
    assert unchanged() == original, (path, "missing token modified SQLite")
    forged = request(page, base, path, payload, "forged-709-token",
                     multipart=multipart, want_json=want_json)
    assert forged.status == 403, (path, "forged", forged.status)
    assert unchanged() == original, (path, "forged token modified SQLite")
    accepted = request(page, base, path, payload, token,
                       multipart=multipart, want_json=want_json)
    assert accepted.status == status, (path, "valid", accepted.status,
                                       accepted.text()[:250])
    assert accepted.headers.get("x-tracker-csrf-report") == "valid"
    if want_json:
        assert accepted.json()["ok"] is True
        assert accepted.json()["updated"] >= 1
    return accepted


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_709_four_food_signed_persisted_workflows(scheme):
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context, page, token = token_context(browser, base, "/food/duplicates")
        seen = set()
        try:
            unique = uuid4().hex[:10]
            nutrients = {key: 0 for key in NUTRIENTS}
            nutrients["energy"] = 100

            # Equivalent records, atomic reference-safe consolidation.
            name = "QA709" + unique + " merge " + scheme
            keeper = seed_food(name, nutrients)
            redundant = seed_food(name, nutrients)
            signed(page, base, "/food/duplicates/merge",
                   {"keep_id": str(keeper), "remove_id": str(redundant)},
                   token, lambda: read(
                       "SELECT COUNT(*) FROM tracker_food_products WHERE id=?",
                       (redundant,),
                   ))
            seen.add(("POST", "/food/duplicates/merge"))
            assert read(
                "SELECT COUNT(*) FROM tracker_food_products WHERE id=?",
                (redundant,),
            ) == (0,)

            # A non-equivalent unused food can be explicitly removed, but
            # not silently merged into historical nutrient values.
            name = "QA709" + unique + " resolve " + scheme
            keep = seed_food(name, nutrients)
            other = seed_food(name, {**nutrients, "energy": 150})
            signed(page, base, "/food/duplicates/resolve-unused",
                   {"keep_id": str(keep), "remove_id": str(other)},
                   token, lambda: read(
                       "SELECT COUNT(*) FROM tracker_food_products WHERE id=?",
                       (other,),
                   ))
            seen.add(("POST", "/food/duplicates/resolve-unused"))
            assert read(
                "SELECT COUNT(*) FROM tracker_food_products WHERE id=?", (other,),
            ) == (0,)

            # A genuinely different duplicate group receives a persisted
            # fingerprint acknowledgement and retains both food products.
            name = "QA709" + unique + " distinct " + scheme
            one = seed_food(name, nutrients)
            two = seed_food(name, {**nutrients, "energy": 175})
            # The legacy duplicate scanner groups by the FIRST TWO name
            # words, including across concurrent HTTP/HTTPS xdist workers.
            # Unique first-word namespace above ensures only these two rows
            # are in the intended group, even while other workers run.
            response = page.goto(base + "/food/duplicates", wait_until="networkidle")
            assert response is not None and response.status == 200
            group = page.locator(
                f'section.food629-group[aria-label="Duplicates of {name}"]'
            )
            assert group.count() == 1, "Distinct-review group not rendered"
            assert set(group.locator(".food629-meta-grid h3").all_inner_texts()) == {
                f"Version #{one}", f"Version #{two}",
            }, "Unrelated food rows leaked into the review group"
            # Read the *real* fingerprint supplied by the application form.
            # Never maintain a duplicate implementation of its hashing.
            fingerprint = group.locator(
                'form[action="/food/duplicates/keep-distinct"] '
                'input[name="fingerprint"]'
            ).input_value()
            assert re.fullmatch(r"[a-f0-9]{64}", fingerprint)
            signed(page, base, "/food/duplicates/keep-distinct",
                   {"fingerprint": fingerprint}, token,
                   lambda: read(
                       "SELECT COUNT(*) FROM tracker_food_duplicate_reviews630 "
                       "WHERE fingerprint=?", (fingerprint,),
                   ))
            seen.add(("POST", "/food/duplicates/keep-distinct"))
            assert read(
                "SELECT COUNT(*) FROM tracker_food_duplicate_reviews630 "
                "WHERE fingerprint=?", (fingerprint,),
            ) == (1,)
            assert read("SELECT COUNT(*) FROM tracker_food_products "
                        "WHERE id IN (?,?)", (one, two)) == (2,)

            name = "QA709" + unique + " editable " + scheme
            food_id = seed_food(name, nutrients)
            response = page.goto(
                base + f"/food/saved/{food_id}/edit?day=2026-11-16",
                wait_until="networkidle",
            )
            assert response is not None and response.status == 200
            version = page.locator('input[name="version"]').input_value()
            assert re.fullmatch(r"[a-f0-9]{64}", version)
            form = {
                "name": name + " updated",
                "serving_description": "170 g",
                "day": "2026-11-16",
                "version": version, "barcode": "",
                **{key: "0" for key in NUTRIENTS},
                "energy": "120",
            }
            path = f"/food/saved/{food_id}/edit"
            signed(page, base, path, form, token,
                   lambda: read(
                       "SELECT name,nutrients FROM tracker_food_products WHERE id=?",
                       (food_id,),
                   ))
            seen.add(("POST", "/food/saved/{product_id}/edit"))
            saved = read(
                "SELECT name,nutrients FROM tracker_food_products WHERE id=?",
                (food_id,),
            )
            assert saved is not None and saved[0] == name + " updated"
            assert json.loads(saved[1])["energy"] == 120.0
            assert seen == FOOD_ROUTES
            print("CSRF_709_FOOD_SIGNED_POSITIVE_ROUTES=4", flush=True)
        finally:
            context.close()
            browser.close()


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_709_six_coa_document_signed_persisted_workflows(scheme):
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context, page, token = token_context(browser, base, "/coas/new")
        seen = set()
        try:
            vial = page.locator(
                'form[action="/coas/new"] select[name="vial_id"] '
                'option:not([value=""])'
            ).first.get_attribute("value")
            assert vial and vial.isdecimal()
            lab = "QA709 COA " + scheme + " " + uuid4().hex[:12]
            bootstrap = request(
                page, base, "/coas/new",
                {"vial_id": vial, "lab_name": lab,
                 "tested_on": "2026-11-16"},
                token,
            )
            assert bootstrap.status == 303
            record = read("SELECT id FROM coas WHERE lab_name=?", (lab,))
            assert record is not None
            cid = record[0]
            assert read("SELECT COUNT(*) FROM coa_attachments WHERE coa_id=?",
                        (cid,)) == (0,)

            path = f"/coas/{cid}/attachments"
            upload = {
                "test_type": "Purity",
                "files": {
                    "name": "qa709-purity.pdf",
                    "mimeType": "application/pdf",
                    "buffer": PDF,
                },
            }
            signed(page, base, path, upload, token,
                   lambda: read("SELECT COUNT(*) FROM coa_attachments WHERE coa_id=?",
                                (cid,)),
                   multipart=True)
            seen.add(("POST", "/coas/{cid}/attachments"))
            attachment = read(
                "SELECT id,test_type,original_name FROM coa_attachments "
                "WHERE coa_id=?", (cid,),
            )
            assert attachment is not None and attachment[1:] == (
                "Purity", "qa709-purity.pdf",
            )
            aid = attachment[0]

            path = f"/coas/{cid}/default-file"
            signed(page, base, path, {"document": str(aid)}, token,
                   lambda: read(
                       "SELECT attachment_id FROM coa_default_documents645 "
                       "WHERE coa_id=?", (cid,),
                   ))
            seen.add(("POST", "/coas/{cid}/default-file"))
            assert read(
                "SELECT attachment_id FROM coa_default_documents645 "
                "WHERE coa_id=?", (cid,),
            ) == (aid,)

            path = f"/coas/{cid}/attachments/{aid}/test-type"
            signed(page, base, path, {"test_type": "Endotoxin"}, token,
                   lambda: read(
                       "SELECT test_type FROM coa_attachments WHERE id=?", (aid,),
                   ))
            seen.add(("POST", "/coas/{cid}/attachments/{aid}/test-type"))
            assert read(
                "SELECT test_type FROM coa_attachments WHERE id=?", (aid,),
            ) == ("Endotoxin",)

            path = f"/coas/{cid}/attachments/test-types"
            signed(page, base, path, {
                f"original_test_type_{aid}": "Endotoxin",
                f"test_type_{aid}": "Sterility",
                f"custom_test_type_{aid}": "",
            }, token,
                   lambda: read(
                       "SELECT test_type FROM coa_attachments WHERE id=?", (aid,),
                   ),
                   status=200, want_json=True)
            seen.add(("POST", "/coas/{cid}/attachments/test-types"))
            assert read(
                "SELECT test_type FROM coa_attachments WHERE id=?", (aid,),
            ) == ("Sterility",)

            path = f"/coas/{cid}/attachments/identifiers"
            signed(page, base, path, {
                f"job_id_{aid}": "QA709-TASK",
                f"verify_code_{aid}": "QA709-VERIFY",
                f"original_job_id_{aid}": "",
                f"original_verify_code_{aid}": "",
            }, token,
                   lambda: read(
                       "SELECT job_id,verify_code FROM coa_attachments WHERE id=?",
                       (aid,),
                   ),
                   status=200, want_json=True)
            seen.add(("POST", "/coas/{cid}/attachments/identifiers"))
            assert read(
                "SELECT job_id,verify_code FROM coa_attachments WHERE id=?", (aid,),
            ) == ("QA709-TASK", "QA709-VERIFY")

            path = f"/coas/{cid}/attachments/{aid}/delete"
            signed(page, base, path, {}, token,
                   lambda: read(
                       "SELECT COUNT(*) FROM coa_attachments WHERE id=?", (aid,),
                   ))
            seen.add(("POST", "/coas/{cid}/attachments/{aid}/delete"))
            assert read(
                "SELECT COUNT(*) FROM coa_attachments WHERE id=?", (aid,),
            ) == (0,)
            assert read(
                "SELECT COUNT(*) FROM coa_default_documents645 WHERE coa_id=?",
                (cid,),
            ) == (0,)
            assert seen == COA_ROUTES
            print("CSRF_709_COA_DOCUMENT_SIGNED_POSITIVE_ROUTES=6", flush=True)
        finally:
            context.close()
            browser.close()
