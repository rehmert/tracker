"""Release 580: real Chromium create/edit/delete strict-CSRF workflows.

This module refuses to collect outside the existing isolated localhost
strict-CSRF browser runner. All mutations are confined to disposable QA data.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import expect, sync_playwright

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
    and DATA.is_dir() and DATA.name == "data"
    and DATA.parent.name.startswith("tracker-browser-qa.")
    and DATA.parent.parent == Path("/tmp").resolve()
):
    raise RuntimeError("Release 580 browser writes require disposable strict localhost")

pytestmark = pytest.mark.browser

OPERATIONS = {
    "compound-lifecycle": (
        ("POST", "/compounds", 303),
        ("POST", "/compounds/{id}/edit", 303),
        ("POST", "/compounds/{id}/delete", 303),
    ),
    "vitals-lifecycle": (
        ("POST", "/vitals", 303),
        ("POST", "/vitals/{id}/edit", 303),
        ("DELETE", "/vitals/{id}", 200),
    ),
    "notes-lifecycle": (
        ("POST", "/pages", 303),
        ("POST", "/pages/{id}", 303),
        ("POST", "/pages/{id}/sources", 303),
        ("POST", "/sources/{id}/delete", 303),
        ("POST", "/pages/{id}/delete", 303),
    ),
}


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        instance = p.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def tab(browser):
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield page, errors
    context.close()


def _visit(page, base, path):
    response = page.goto(base + path, wait_until="networkidle")
    assert response is not None and response.status == 200, (path, response.status)
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")
    return token


def _record(scheme, flow, observed):
    assert flow in OPERATIONS
    assert tuple(observed) == OPERATIONS[flow]
    directory = DATA.parent / "csrf-runtime580"
    directory.mkdir(mode=0o700, exist_ok=True)
    destination = directory / f"{scheme}-{flow}.json"
    payload = {
        "scheme": scheme, "flow": flow, "operations": [
            {"method": method, "route_pattern": path, "signed_status": status,
             "unsigned_status": 403}
            for method, path, status in observed
        ],
        "isolated_strict_browser": True,
        "real_user_interactions": True,
    }
    with destination.open("x", encoding="utf-8") as output:
        json.dump(payload, output, sort_keys=True)
        output.write("\n")
    destination.chmod(0o600)


def _submit(page, locator, method, path, expected):
    with page.expect_response(lambda response: (
        response.request.method == method
        and urlsplit(response.url).path == path
    )) as pending:
        locator.click()
    response = pending.value
    assert response.status == expected, (method, path, response.status)
    assert response.headers.get("x-tracker-csrf-report") == "valid"
    return response


def _forgery(page, base, method, path, **kwargs):
    response = page.request.fetch(
        base + path, method=method, max_redirects=0, **kwargs
    )
    assert response.status == 403, (method, path, response.status)


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_580_compound_create_edit_delete_real_native_forms(tab, scheme):
    page, errors = tab
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    token = _visit(page, base, "/compounds")
    name = "QA 580 compound " + uuid4().hex[:12]
    create = page.locator('form[method="post"][action="/compounds"]')
    assert create.count() == 1
    assert create.locator('input[name="csrf_token"]').input_value() == token
    _forgery(page, base, "POST", "/compounds", data={"name": "QA forged 580"})
    create.locator('input[name="name"]').fill(name)
    _submit(page, create.get_by_role("button", name="Add compound"), "POST", "/compounds", 303)
    expect(page.locator("body")).to_contain_text(name)

    row = page.locator("tr").filter(has_text=name)
    expect(row).to_have_count(1)
    edit_path = row.locator('a[href$="/edit"]').get_attribute("href")
    assert edit_path and re.fullmatch(r"/compounds/[0-9]+/edit", edit_path)
    token = _visit(page, base, edit_path)
    edit = page.locator('form[method="post"][action="' + edit_path + '"]')
    assert edit.count() == 1
    assert edit.locator('input[name="csrf_token"]').input_value() == token
    _forgery(page, base, "POST", edit_path, data={"name": "QA forged edit 580"})
    changed = name + " edited"
    edit.locator('input[name="name"]').fill(changed)
    _submit(page, edit.get_by_role("button", name="Save changes"), "POST", edit_path, 303)
    expect(page.locator("body")).to_contain_text(changed)

    row = page.locator("tr").filter(has_text=changed)
    expect(row).to_have_count(1)
    delete_path = row.locator('form[action$="/delete"]').get_attribute("action")
    assert delete_path and re.fullmatch(r"/compounds/[0-9]+/delete", delete_path)
    _forgery(page, base, "POST", delete_path)
    expect(row).to_have_count(1)
    page.on("dialog", lambda dialog: dialog.accept())
    _submit(page, row.locator('form[action$="/delete"] button'), "POST", delete_path, 303)
    expect(page.locator("body")).not_to_contain_text(changed)
    assert not errors, errors
    _record(scheme, "compound-lifecycle", OPERATIONS["compound-lifecycle"])


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_580_vitals_create_edit_htmx_delete(tab, scheme):
    page, errors = tab
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    token = _visit(page, base, "/vitals")
    label = "QA strict vitals 580 " + uuid4().hex[:10]
    form = page.locator('form[action="/vitals"][method="post"]')
    assert form.count() == 1
    assert form.locator('input[name="csrf_token"]').input_value() == token
    _forgery(page, base, "POST", "/vitals", data={"weight": "190", "context": "forged"})
    form.locator('input[name="weight"]').fill("191.5")
    form.locator('input[name="context"]').fill(label)
    _submit(page, form.get_by_role("button", name="Save reading"), "POST", "/vitals", 303)
    row = page.locator("tr").filter(has_text=label)
    expect(row).to_have_count(1)
    edit_url = row.locator('a[href*="/edit"]').get_attribute("href")
    assert edit_url
    edit_path = urlsplit(edit_url).path
    assert re.fullmatch(r"/vitals/[0-9]+/edit", edit_path)
    token = _visit(page, base, edit_path)
    edit = page.locator('form[action="' + edit_path + '"][method="post"]')
    assert edit.count() == 1
    assert edit.locator('input[name="csrf_token"]').input_value() == token
    _forgery(page, base, "POST", edit_path, data={"context": "forged edit"})
    changed = label + " updated"
    edit.locator('input[name="context"]').fill(changed)
    _submit(page, edit.get_by_role("button", name="Save Changes"), "POST", edit_path, 303)
    row = page.locator("tr").filter(has_text=changed)
    expect(row).to_have_count(1)
    delete_path = row.locator('button[hx-delete]').get_attribute("hx-delete")
    assert delete_path and re.fullmatch(r"/vitals/[0-9]+", delete_path)
    _forgery(page, base, "DELETE", delete_path)
    expect(row).to_have_count(1)
    page.on("dialog", lambda dialog: dialog.accept())
    _submit(page, row.locator('button[hx-delete]'), "DELETE", delete_path, 200)
    expect(page.locator("tr").filter(has_text=changed)).to_have_count(0)
    assert not errors, errors
    _record(scheme, "vitals-lifecycle", OPERATIONS["vitals-lifecycle"])


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_580_notes_create_edit_delete_real_forms(tab, scheme):
    page, errors = tab
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    token = _visit(page, base, "/pages/new")
    title = "QA strict notes 580 " + uuid4().hex[:12]
    form = page.locator('form[method="post"][action="/pages"]')
    assert form.count() == 1
    assert form.locator('input[name="csrf_token"]').input_value() == token
    _forgery(page, base, "POST", "/pages", data={"title": "QA forged 580"})
    form.locator('input[name="title"]').fill(title)
    _submit(page, form.get_by_role("button", name="Save page"), "POST", "/pages", 303)
    page.wait_for_url(re.compile(re.escape(base) + r"/pages/[0-9]+(?:\?.*)?$"))
    pid = urlsplit(page.url).path.split("/")[-1]
    assert pid.isdecimal()
    edit_path = "/pages/" + pid
    token = _visit(page, base, edit_path + "/edit")
    edit = page.locator('form[method="post"][action="' + edit_path + '"]')
    assert edit.count() == 1
    assert edit.locator('input[name="csrf_token"]').input_value() == token
    _forgery(page, base, "POST", edit_path, data={"title": "QA forged edit"})
    changed = title + " updated"
    edit.locator('input[name="title"]').fill(changed)
    _submit(page, edit.get_by_role("button", name="Save page"), "POST", edit_path, 303)
    expect(page.locator("h1")).to_contain_text(changed)

    # Add a source through the actual Notes UI, then confirm unsigned
    # deletion is denied and signed deletion succeeds.
    source_path = edit_path + "/sources"
    source_form = page.locator('form[method="post"][action="' + source_path + '"]')
    assert source_form.count() == 1
    assert source_form.locator('input[name="csrf_token"]').count() == 1
    _forgery(page, base, "POST", source_path, data={"title": "forged source"})
    source_title = "QA source 580 " + uuid4().hex[:10]
    source_form.locator('input[name="title"]').fill(source_title)
    _submit(page, source_form.get_by_role("button", name="Add source"),
            "POST", source_path, 303)
    expect(page.locator("body")).to_contain_text(source_title)
    source_row = page.locator("li").filter(has_text=source_title)
    expect(source_row).to_have_count(1)
    source_delete = source_row.locator('form[action$="/delete"]')
    source_delete_path = source_delete.get_attribute("action")
    assert source_delete_path and re.fullmatch(r"/sources/[0-9]+/delete",
                                                 source_delete_path)
    _forgery(page, base, "POST", source_delete_path)
    page.on("dialog", lambda dialog: dialog.accept())
    _submit(page, source_delete.get_by_role("button", name="Remove"),
            "POST", source_delete_path, 303)
    expect(page.locator("body")).not_to_contain_text(source_title)
    delete_path = edit_path + "/delete"
    delete = page.locator('form[method="post"][action="' + delete_path + '"]')
    assert delete.count() == 1
    assert delete.locator('input[name="csrf_token"]').count() == 1
    _forgery(page, base, "POST", delete_path)
    _submit(page, delete.get_by_role("button", name="Delete page"), "POST", delete_path, 303)
    expect(page.locator("body")).not_to_contain_text(changed)
    assert page.request.get(base + edit_path).status == 404
    assert not errors, errors
    _record(scheme, "notes-lifecycle", OPERATIONS["notes-lifecycle"])


@pytest.mark.parametrize("scheme", ("http", "https"))
@pytest.mark.parametrize("path", (
    "/compounds", "/vitals", "/pages", "/pages/preview",
))
def test_580_hostile_origin_denied_on_unsafe_existing_routes(tab, scheme, path):
    page, errors = tab
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    _visit(page, base, "/compounds")
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    rejected = page.request.post(
        base + path,
        data={"name": "QA origin forged 580", "title": "QA origin forged 580"},
        headers={"X-Tracker-CSRF": token, "Origin": "https://attacker.invalid"},
        max_redirects=0,
    )
    assert rejected.status == 403, (scheme, path, rejected.status)
    assert not errors, errors
