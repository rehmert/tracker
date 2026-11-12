"""Release 521: real Chromium strict-CSRF acceptance on disposable localhost.

Only collected by tracker-browser-qualify.sh against its isolated candidate.
Never imports or uses credentials, data, or endpoints from the installed app.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import expect, sync_playwright

URL = os.environ.get("TRACKER_TEST_URL", "").rstrip("/")
HTTPS_URL = os.environ.get("TRACKER_TEST_HTTPS_URL", "").rstrip("/")
DATA = Path(os.environ.get("TRACKER_BROWSER_QA_DATA_DIR", "/")).resolve()
HTTP = urlsplit(URL)
HTTPS = urlsplit(HTTPS_URL)

if not (
    os.environ.get("TRACKER_TEST_ISOLATED") == "1"
    and os.environ.get("TRACKER_TEST_STRICT_CSRF") == "1"
    and HTTP.scheme == "http"
    and HTTPS.scheme == "https"
    and HTTP.hostname == HTTPS.hostname == "127.0.0.1"
    and HTTP.port not in (None, 8000)
    and HTTPS.port not in (None, 443, 8000, HTTP.port)
    and DATA.is_dir()
    and DATA.name == "data"
    and DATA.parent.name.startswith("tracker-browser-qa.")
    and DATA.parent.parent == Path("/tmp").resolve()
):
    raise RuntimeError(
        "Strict browser writes require isolated HTTPS localhost candidate"
    )

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True)
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


def _navigate(page, path):
    response = page.goto(HTTPS_URL + path, wait_until="networkidle")
    assert response is not None and response.status == 200, (
        path, None if response is None else response.status
    )
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1."), "Real browser did not receive signed token"
    return token


def _post_response(page, path):
    return lambda response: (
        response.request.method in ("POST", "DELETE")
        and urlsplit(response.url).path == path
    )


def _verified(response, *, status):
    assert response.status == status, (
        response.status, response.text()[:150]
    )
    assert response.headers.get("x-tracker-csrf-report") == "valid", (
        response.headers.get("x-tracker-csrf-report")
    )


def test_521_native_urlencoded_compound_create_and_reject_forgery(tab):
    page, errors = tab
    _navigate(page, "/compounds")
    form = page.locator('form[action="/compounds"][method="post"]')
    assert form.count() == 1
    assert form.locator('input[name="csrf_token"]').count() == 1
    name = "QA strict native compound 521"
    form.locator('input[name="name"]').fill(name)
    with page.expect_response(_post_response(page, "/compounds")) as pending:
        form.get_by_role("button", name="Add compound").click()
    _verified(pending.value, status=303)
    expect(page.locator("body")).to_contain_text(name)

    # Browser API requests share the cookie but do NOT run our fetch wrapper.
    # This deliberately omits the submitted CSRF token and must fail closed.
    denied = page.request.post(
        HTTPS_URL + "/compounds",
        data={"name": "QA forged compound 521"},
        max_redirects=0,
    )
    assert denied.status == 403
    _navigate(page, "/compounds")
    assert "QA forged compound 521" not in page.locator("body").inner_text()
    assert not errors, errors


def test_521_native_coa_multipart_upload_and_signed_verification(tab):
    page, errors = tab
    _navigate(page, "/coas/new")
    form = page.locator('form[action="/coas/new"]')
    assert form.count() == 1
    assert form.locator('input[name="csrf_token"]').count() == 1
    choices = form.locator('select[name="vial_id"] option:not([value=""])')
    assert choices.count() >= 1, "Disposable vial fixtures are missing"
    vial = choices.first.get_attribute("value")
    assert vial and vial.isdecimal()
    form.locator('select[name="vial_id"]').select_option(vial)
    form.locator('input[name="lab_name"]').fill("QA strict COA 521")
    form.locator('input[name="tested_on"]').fill("2026-11-08")
    form.locator('input[name="file"]').set_input_files({
        "name": "strict-coa521.pdf",
        "mimeType": "application/pdf",
        "buffer": b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n",
    })
    with page.expect_response(_post_response(page, "/coas/new")) as pending:
        form.get_by_role("button", name="Create COA").click()
    _verified(pending.value, status=303)
    page.wait_for_url(re.compile(re.escape(HTTPS_URL) + r"/coas/[0-9]+(?:\?.*)?$"))
    expect(page.locator("body")).to_contain_text("QA strict COA 521")
    assert page.locator("body").get_by_text("strict-coa521.pdf").count() >= 1
    coa_id = urlsplit(page.url).path.split("/")[-1]
    page.locator('form[action="/coas/' + coa_id + '/verify"] select[name="status"]').select_option(index=0)
    with page.expect_response(
        _post_response(page, f"/coas/{coa_id}/verify")
    ) as verify_response:
        page.locator('form[action="/coas/' + coa_id + '/verify"] button').click()
    _verified(verify_response.value, status=303)

    # Real upload without token must be rejected rather than creating a COA.
    rejected = page.request.post(
        HTTPS_URL + "/coas/new",
        multipart={
            "vial_id": vial,
            "lab_name": "QA forbidden COA 521",
            "file": {
                "name": "forged.pdf",
                "mimeType": "application/pdf",
                "buffer": b"%PDF-1.4\n%%EOF\n",
            },
        },
        max_redirects=0,
    )
    assert rejected.status == 403
    assert "QA forbidden COA 521" not in page.request.get(
        HTTPS_URL + "/coas"
    ).text()
    assert not errors, errors


def test_521_htmx_preview_writes_include_signed_header(tab):
    page, errors = tab
    _navigate(page, "/pages/new")
    editor = page.locator("#notes-body")
    assert editor.get_attribute("hx-post") == "/pages/preview"

    # New notes open in Visual mode by default, so their Markdown textarea
    # is intentionally hidden. Switch modes through the actual UI rather
    # than forcing input into a hidden element (Playwright rejects that).
    page.locator("#notes-source-mode").click()
    expect(page.locator("#notes-source-mode")).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(editor).to_be_visible()

    with page.expect_response(_post_response(page, "/pages/preview")) as pending:
        editor.fill("**Strict HTMX preview 521**")
    _verified(pending.value, status=200)
    expect(page.locator("#preview")).to_contain_text(
        "Strict HTMX preview 521"
    )
    assert not errors, errors


def test_521_same_origin_fetch_auto_header_and_missing_header_denial(tab):
    page, errors = tab
    token = _navigate(page, "/compounds")
    requests = []

    def capture(request):
        if request.method == "POST" and urlsplit(request.url).path == "/compounds":
            requests.append(request.all_headers())

    page.on("request", capture)
    name = "QA strict fetch compound 521"
    result = page.evaluate(
        """async name => {
          const fields = new URLSearchParams({
            name, category: 'peptide', primary_unit: 'mg'
          });
          const response = await fetch('/compounds', {
            method: 'POST', body: fields
          });
          return {
            status: response.status,
            redirected: response.redirected
          };
        }""",
        name,
    )
    assert result == {"status": 200, "redirected": True}, result
    assert requests and requests[-1].get("x-tracker-csrf") == token
    _navigate(page, "/compounds")
    expect(page.locator("body")).to_contain_text(name)
    denied = page.request.post(
        HTTPS_URL + "/pk/compounds",
        data="{}",
        headers={"Content-Type": "application/json"},
        max_redirects=0,
    )
    assert denied.status == 403
    assert not errors, errors


def test_521_htmx_delete_vitals_needs_token_and_preserves_other_records(tab):
    page, errors = tab
    _navigate(page, "/vitals")
    form = page.locator('form[action="/vitals"][method="post"]')
    form.locator('input[name="weight"]').fill("180")
    form.locator('input[name="context"]').fill("QA STRICT VITAL 521")
    with page.expect_response(_post_response(page, "/vitals")) as pending:
        form.get_by_role("button", name="Save reading").click()
    _verified(pending.value, status=303)
    row = page.locator("tr").filter(has_text="QA STRICT VITAL 521")
    expect(row).to_have_count(1)
    button = row.locator('button[hx-delete]')
    url = urlsplit(button.get_attribute("hx-delete") or "").path
    assert re.fullmatch(r"/vitals/[0-9]+", url)
    page.on("dialog", lambda dialog: dialog.accept())
    with page.expect_response(_post_response(page, url)) as pending:
        button.click()
    _verified(pending.value, status=200)
    expect(page.locator("tr").filter(has_text="QA STRICT VITAL 521")).to_have_count(0)
    assert not errors, errors


# Release 573: broader real browser coverage. These tests are automatically
# run by the existing strict browser worker against disposable HTTP and
# host-rewriting HTTPS candidates. No installed Tracker URL is permitted.
@pytest.mark.parametrize("origin", ("http", "https"))
@pytest.mark.parametrize("path", (
    "/compounds", "/vials", "/purchases", "/supplies",
    "/vitals", "/blends", "/food", "/protocols",
))
def test_573_native_write_forms_have_signed_tokens_on_http_and_https(
    tab, origin, path,
):
    page, errors = tab
    base = URL if origin == "http" else HTTPS_URL
    response = page.goto(base + path, wait_until="networkidle")
    assert response is not None and response.status == 200, (origin, path)
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1."), (origin, path)

    forms = page.locator('form[method="post" i]')
    assert forms.count() >= 1, ("Missing expected native POST form", path)
    for index in range(forms.count()):
        form = forms.nth(index)
        own_origin = form.evaluate(
            "form => new URL(form.action, location.href).origin === location.origin"
        )
        if not own_origin:
            continue
        fields = form.locator('input[name="csrf_token"]')
        assert fields.count() == 1, (origin, path, index)
        assert fields.first.input_value() == token, (origin, path, index)
    assert not errors, (origin, path, errors)


@pytest.mark.parametrize("origin", ("http", "https"))
def test_573_valid_signed_fetch_works_on_both_localhost_schemes(tab, origin):
    page, errors = tab
    base = URL if origin == "http" else HTTPS_URL
    response = page.goto(base + "/compounds", wait_until="networkidle")
    assert response is not None and response.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")

    intercepted = []
    page.on("request", lambda request: intercepted.append(request.all_headers())
            if request.method == "POST" and
               urlsplit(request.url).path == "/compounds" else None)

    # Missing required compound name makes this a no-mutation positive
    # CSRF proof: the existing endpoint returns 422 after token validation.
    outcome = page.evaluate("""async () => {
        const fields = new URLSearchParams({name: ''});
        const response = await fetch('/compounds', {
            method: 'POST', body: fields
        });
        return {
            status: response.status,
            report: response.headers.get('x-tracker-csrf-report')
        };
    }""")
    assert outcome == {"status": 422, "report": "valid"}, outcome
    assert intercepted and intercepted[-1].get("x-tracker-csrf") == token
    assert not errors, errors


@pytest.mark.parametrize("origin", ("http", "https"))
def test_573_strict_unsafe_unnsigned_requests_fail_on_both_schemes(tab, origin):
    page, errors = tab
    base = URL if origin == "http" else HTTPS_URL
    response = page.goto(base + "/compounds", wait_until="networkidle")
    assert response is not None and response.status == 200

    # Playwright API requests bypass Tracker's browser fetch wrapper. This
    # deliberately omits the signed header/form token and must be denied.
    denied = page.request.post(
        base + "/compounds", data={"name": ""},
        max_redirects=0,
    )
    assert denied.status == 403
    assert "CSRF token required" in denied.text()
    assert not errors, errors


# Release 574: extend browser checks to write-heavy native form views that
# were not included in the original Release 573 eight-page matrix.
# Strict mode is ONLY enabled on the disposable candidate/HTTPS proxy.
@pytest.mark.parametrize("origin", ("http", "https"))
@pytest.mark.parametrize("path", (
    "/vendor-prices", "/labs/new", "/coas/new", "/pages/new",
))
def test_574_more_native_forms_have_signed_token_fields(tab, origin, path):
    page, errors = tab
    base = URL if origin == "http" else HTTPS_URL
    response = page.goto(base + path, wait_until="networkidle")
    assert response is not None and response.status == 200, (origin, path)
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1."), (origin, path)

    forms = page.locator('form[method="post" i]')
    assert forms.count() >= 1, (origin, path, "Expected native write form")
    checked = 0
    for index in range(forms.count()):
        form = forms.nth(index)
        if not form.evaluate(
            "form => new URL(form.action, location.href).origin === location.origin"
        ):
            continue
        fields = form.locator('input[name="csrf_token"]')
        assert fields.count() == 1, (origin, path, index)
        assert fields.first.input_value() == token, (origin, path, index)
        checked += 1
    assert checked >= 1
    assert not errors, (origin, path, errors)


@pytest.mark.parametrize("origin", ("http", "https"))
def test_574_rendered_dynamic_compound_action_is_tokenized_and_forgery_denied(
    tab, origin,
):
    page, errors = tab
    base = URL if origin == "http" else HTTPS_URL
    response = page.goto(base + "/compounds", wait_until="networkidle")
    assert response is not None and response.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")

    # The disposable browser QA runner creates QA Alpha/Zeta compounds.
    # Inspect an actual Jinja-rendered delete route; do NOT delete anything.
    forms = page.locator(
        'form[method="post"][action^="/compounds/"][action$="/delete"]'
    )
    assert forms.count() >= 1, "Expected disposable compound delete form"
    form = forms.first
    action = form.get_attribute("action")
    assert action and re.fullmatch(r"/compounds/[0-9]+/delete", action)
    field = form.locator('input[name="csrf_token"]')
    assert field.count() == 1
    assert field.first.input_value() == token

    # Bypass browser JS intentionally. Without the signed form field/header
    # strict mode must block the destructive route before any mutation.
    forged = page.request.post(base + action, data={}, max_redirects=0)
    assert forged.status == 403
    assert "CSRF token required" in forged.text()
    assert not errors, errors


@pytest.mark.parametrize("origin", ("http", "https"))
def test_574_request_object_fetch_receives_signed_header_under_strict_csrf(
    tab, origin,
):
    page, errors = tab
    base = URL if origin == "http" else HTTPS_URL
    response = page.goto(base + "/compounds", wait_until="networkidle")
    assert response is not None and response.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")

    captures = []
    def capture(request):
        if (request.method == "POST" and
                urlsplit(request.url).path == "/compounds"):
            captures.append(request.all_headers())

    page.on("request", capture)
    # Testing fetch(Request), not fetch(url, options) as Release 573 did.
    # Empty required name returns 422 without writing a record.
    result = page.evaluate("""async () => {
        const body = new URLSearchParams({name: ''});
        const request = new Request('/compounds', {
            method: 'POST',
            body,
            credentials: 'same-origin'
        });
        const response = await fetch(request);
        return {
            status: response.status,
            csrf: response.headers.get('x-tracker-csrf-report')
        };
    }""")
    assert result == {"status": 422, "csrf": "valid"}, result
    assert captures and captures[-1].get("x-tracker-csrf") == token
    assert not errors, errors


# Release 575: executable positive-write tests for previously unresolved
# Jinja actions and mobile quick-entry forms. All activity is confined to
# the browser runner's disposable strict-CSRF localhost backend.
@pytest.mark.parametrize("scheme", ("http", "https"))
@pytest.mark.parametrize("kind,endpoint,values", (
    ("weight", "/vitals", {"weight": "212.5"}),
    ("bp", "/vitals", {"systolic": "122", "diastolic": "78"}),
    ("water", "/food/water", {"ounces": "6.5"}),
))
def test_575_mobile_quick_entry_signed_fetch_and_implicit_forms(
    tab, scheme, kind, endpoint, values,
):
    page, errors = tab
    page.set_viewport_size({"width": 390, "height": 844})
    base = URL if scheme == "http" else HTTPS_URL
    response = page.goto(base + "/mobile", wait_until="networkidle")
    assert response is not None and response.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")

    # These forms intentionally omit action=; JavaScript sends them to their
    # data-quick528-endpoint. CSRF must survive that fetch/FormData path.
    for entry_kind, entry_endpoint in (
        ("weight", "/vitals"), ("bp", "/vitals"), ("water", "/food/water"),
    ):
        form = page.locator(f'form[data-quick528-form="{entry_kind}"]')
        assert form.count() == 1
        assert form.get_attribute("action") is None
        assert form.get_attribute("data-quick528-endpoint") == entry_endpoint
        field = form.locator('input[name="csrf_token"]')
        assert field.count() == 1, entry_kind
        assert field.input_value() == token, entry_kind

    requests = []
    def capture(request):
        if request.method == "POST" and urlsplit(request.url).path == endpoint:
            requests.append(request.all_headers())

    page.on("request", capture)
    trigger = page.locator("#tracker-mobile-add528")
    assert trigger.count() == 1
    trigger.click()
    page.locator(f'[data-quick528-choice="{kind}"]').click()
    form = page.locator(f'form[data-quick528-form="{kind}"]')
    for field, value in values.items():
        form.locator(f'input[name="{field}"]').fill(value)
    with page.expect_response(_post_response(page, endpoint)) as pending:
        form.locator('button[type="submit"]').click()
    _verified(pending.value, status=200)
    expect(page.locator("[data-quick528-success]")).to_be_visible()
    assert requests and requests[-1].get("x-tracker-csrf") == token
    assert not errors, errors

@pytest.mark.parametrize("scheme", ("http", "https"))
def test_575_create_and_edit_notes_with_rendered_dynamic_action(tab, scheme):
    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    response = page.goto(base + "/pages/new", wait_until="networkidle")
    assert response is not None and response.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")

    form = page.locator('form[method="post"][action="/pages"]')
    assert form.count() == 1
    assert form.locator('input[name="csrf_token"]').input_value() == token

    title = "QA CSRF note 575 " + uuid4().hex[:12]
    form.locator('input[name="title"]').fill(title)
    with page.expect_response(_post_response(page, "/pages")) as pending:
        form.get_by_role("button", name="Save page").click()
    _verified(pending.value, status=303)

    page.wait_for_url(re.compile(re.escape(base) + r"/pages/[0-9]+(?:\?.*)?$"))
    pid = urlsplit(page.url).path.rsplit("/", 1)[-1]
    assert pid.isdecimal()
    edit_url = base + "/pages/" + pid + "/edit"
    response = page.goto(edit_url, wait_until="networkidle")
    assert response is not None and response.status == 200
    form = page.locator(f'form[method="post"][action="/pages/{pid}"]')
    assert form.count() == 1
    assert form.locator('input[name="csrf_token"]').input_value() == token

    # Forged native edit must not touch the just-created QA page.
    denied = page.request.post(
        base + "/pages/" + pid,
        data={"title": "Forged CSRF 575"},
        max_redirects=0,
    )
    assert denied.status == 403

    updated = title + " edited"
    form.locator('input[name="title"]').fill(updated)
    with page.expect_response(_post_response(page, "/pages/" + pid)) as pending:
        form.get_by_role("button", name="Save page").click()
    _verified(pending.value, status=303)
    page.wait_for_url(re.compile(re.escape(base) + r"/pages/[0-9]+(?:\?.*)?$"))
    expect(page.locator("body")).to_contain_text(updated)
    assert "Forged CSRF 575" not in page.locator("body").inner_text()
    assert not errors, errors


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_575_coa_create_edit_rendered_action_and_multipart_positive(
    tab, scheme,
):
    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    response = page.goto(base + "/coas/new", wait_until="networkidle")
    assert response is not None and response.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")
    form = page.locator('form[method="post"][action="/coas/new"]')
    assert form.count() == 1
    assert form.locator('input[name="csrf_token"]').input_value() == token
    choices = form.locator('select[name="vial_id"] option:not([value=""])')
    assert choices.count() >= 1, "Isolated COA vial fixtures missing"
    vial = choices.first.get_attribute("value")
    assert vial and vial.isdecimal()
    form.locator('select[name="vial_id"]').select_option(vial)
    lab = "QA CSRF 575 " + uuid4().hex[:12]
    form.locator('input[name="lab_name"]').fill(lab)
    with page.expect_response(_post_response(page, "/coas/new")) as pending:
        form.get_by_role("button", name="Create COA").click()
    _verified(pending.value, status=303)
    page.wait_for_url(re.compile(re.escape(base) + r"/coas/[0-9]+(?:\?.*)?$"))
    cid = urlsplit(page.url).path.rsplit("/", 1)[-1]
    assert cid.isdecimal()

    # The same template chooses a completely different Jinja action on edit.
    form = page.locator(f'form[method="post"][action="/coas/{cid}/edit"]')
    assert form.count() == 1
    assert form.locator('input[name="csrf_token"]').input_value() == token
    denied = page.request.post(
        base + "/coas/" + cid + "/edit",
        multipart={"lab_name": "Forged COA 575"},
        max_redirects=0,
    )
    assert denied.status == 403

    lab_updated = lab + " edit"
    form.locator('input[name="lab_name"]').fill(lab_updated)
    with page.expect_response(_post_response(page, "/coas/" + cid + "/edit")) as pending:
        form.get_by_role("button", name="Save changes").click()
    _verified(pending.value, status=303)
    expect(page.locator("body")).to_contain_text(lab_updated)
    assert "Forged COA 575" not in page.locator("body").inner_text()
    assert not errors, errors


# Release 576: positive + forged-native correction against disposable
# preparation fixtures, on HTTP and host-rewriting HTTPS.
@pytest.mark.parametrize("scheme,fixture_name", (
    ("http", "QA Alpha 511"),
    ("https", "QA Zeta 511"),
))
def test_576_preparation_implicit_action_positive_and_forgery(tab, scheme, fixture_name):
    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    response = page.goto(base + "/vials?status=all", wait_until="networkidle")
    assert response is not None and response.status == 200
    links = page.locator('a[href^="/vials/"]').filter(has_text=fixture_name + " vial")
    assert links.count() == 1, fixture_name
    vial_path = links.first.get_attribute("href")
    assert vial_path and re.fullmatch(r"/vials/[0-9]+", vial_path)
    response = page.goto(base + vial_path, wait_until="networkidle")
    assert response is not None and response.status == 200
    events = page.locator(
        'a[href^="' + vial_path + '/preparations/"][href$="/edit"]'
    )
    assert events.count() >= 1
    edit_path = events.first.get_attribute("href")
    assert edit_path and re.fullmatch(
        re.escape(vial_path) + r"/preparations/[0-9]+/edit", edit_path
    )
    response = page.goto(base + edit_path, wait_until="networkidle")
    assert response is not None and response.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")

    # Native form intentionally has no action= attribute: browser sends
    # the request to the current rendered edit URL.
    form = page.locator('form[method="post"].grid')
    assert form.count() == 1
    assert form.get_attribute("action") is None
    assert form.locator('input[name="csrf_token"]').input_value() == token
    original = form.locator('input[name="notes"]').input_value()
    assert "QA disposable preparation 576" in original

    forged = "QA forged preparation 576"
    denied = page.request.post(
        base + edit_path, data={"notes": forged}, max_redirects=0,
    )
    assert denied.status == 403
    response = page.reload(wait_until="networkidle")
    assert response is not None and response.status == 200
    form = page.locator('form[method="post"].grid')
    assert form.locator('input[name="notes"]').input_value() == original

    corrected = original + " corrected"
    form.locator('input[name="notes"]').fill(corrected)
    with page.expect_response(_post_response(page, edit_path)) as pending:
        form.get_by_role("button", name="Save correction").click()
    _verified(pending.value, status=303)
    page.wait_for_url(re.compile(re.escape(base + vial_path) + r"(?:\\?.*)?$"))
    expect(page.locator("body")).to_contain_text(corrected)
    assert forged not in page.locator("body").inner_text()
    assert not errors, errors
