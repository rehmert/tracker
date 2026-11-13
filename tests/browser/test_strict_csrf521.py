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
    # Other disposable browser tests may create additional vials with
    # similar names. Identify the preparation fixture by its unique
    # event marker, not by an assumed unique human-readable vial label.
    links = page.locator('a[href^="/vials/"]').filter(has_text=fixture_name + " vial")
    candidate_paths = sorted({
        value for value in links.evaluate_all(
            "elements => elements.map(element => element.getAttribute('href'))"
        )
        if value and re.fullmatch(r"/vials/[0-9]+", value)
    })
    assert candidate_paths, ("Missing disposable vial candidates", fixture_name)
    expected_note = "QA disposable preparation 576 " + fixture_name
    matches = []
    for candidate in candidate_paths:
        response = page.goto(base + candidate, wait_until="networkidle")
        assert response is not None and response.status == 200
        if expected_note in (page.locator("body").text_content() or ""):
            matches.append(candidate)
    assert len(matches) == 1, (
        "Expected exactly one isolated preparation fixture", fixture_name, matches
    )
    vial_path = matches[0]
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
    page.wait_for_url(re.compile(re.escape(base + vial_path) + r"(?:\?.*)?$"))
    expect(page.locator("body")).to_contain_text(corrected)
    assert forged not in page.locator("body").inner_text()
    assert not errors, errors

# Release 577: browser-network negative matrices against only the isolated
# localhost candidate. The signed token is deliberately supplied alongside
# a hostile Origin, proving a valid token alone cannot override origin policy.
@pytest.mark.parametrize("scheme", ("http", "https"))
@pytest.mark.parametrize("request_case", ("json", "multipart", "large-json"))
def test_577_cross_site_signed_token_still_rejected(tab, scheme, request_case):
    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    response = page.goto(base + "/compounds", wait_until="networkidle")
    assert response is not None and response.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")
    headers = {
        "Origin": "https://untrusted.invalid",
        "Sec-Fetch-Site": "cross-site",
        "X-Tracker-CSRF": token,
    }
    if request_case == "multipart":
        denied = page.request.post(
            base + "/coas/new",
            multipart={"lab_name": "QA rejected 577", "file": {
                "name": "untrusted.pdf", "mimeType": "application/pdf",
                "buffer": b"%PDF-1.4\\n%%EOF\\n",
            }},
            headers=headers, max_redirects=0,
        )
    else:
        body = '{"name":"' + ("x" * 131072 if request_case == "large-json"
                             else "QA untrusted 577") + '"}'
        denied = page.request.post(
            base + "/pk/compounds",
            data=body,
            headers={**headers, "Content-Type": "application/json"},
            max_redirects=0,
        )
    expected_statuses = (403, 413) if request_case == "large-json" else (403,)
    assert denied.status in expected_statuses, (scheme, request_case, denied.status)
    assert not errors, errors


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_577_same_origin_unsigned_large_json_denied(tab, scheme):
    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    response = page.goto(base + "/compounds", wait_until="networkidle")
    assert response is not None and response.status == 200
    denied = page.request.post(
        base + "/pk/compounds",
        data='{"name":"' + "x" * 131072 + '"}',
        headers={"Content-Type": "application/json"},
        max_redirects=0,
    )
    assert denied.status in (403, 413)
    assert not errors, errors


# Release 578: explicit browser-bound unsafe-route negative compatibility
# matrix. No installed routes or data are contacted; this test is executed
# only after the isolated strict-CSRF startup probe.
@pytest.mark.parametrize("scheme", ("http", "https"))
@pytest.mark.parametrize("scenario", (
    "missing-token", "forged-token", "cross-site-valid-token",
    "cross-site-no-token", "wrong-origin-valid-token", "tampered-form-token",
))
def test_578_native_compound_write_negative_matrix(tab, scheme, scenario):
    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    response = page.goto(base + "/compounds", wait_until="networkidle")
    assert response is not None and response.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")
    name = "QA denied strict 578 " + scheme + " " + scenario
    data = {"name": name}
    headers = {}
    if scenario == "forged-token":
        data["csrf_token"] = "not-a-signed-token"
    elif scenario == "cross-site-valid-token":
        data["csrf_token"] = token
        headers = {
            "Origin": "https://attacker.invalid",
            "Sec-Fetch-Site": "cross-site",
        }
    elif scenario == "cross-site-no-token":
        headers = {
            "Origin": "https://attacker.invalid",
            "Sec-Fetch-Site": "cross-site",
        }
    elif scenario == "wrong-origin-valid-token":
        data["csrf_token"] = token
        headers = {"Origin": "https://attacker.invalid"}
    elif scenario == "tampered-form-token":
        data["csrf_token"] = token[:6] + ("A" if token[6] != "A" else "B") + token[7:]

    denied = page.request.post(
        base + "/compounds", data=data, headers=headers,
        max_redirects=0,
    )
    assert denied.status == 403, (scheme, scenario, denied.status)
    assert not errors, errors


@pytest.mark.parametrize("scheme", ("http", "https"))
@pytest.mark.parametrize("method", ("POST", "PUT", "PATCH", "DELETE"))
def test_578_unsafe_method_without_csrf_never_mutates_compounds(
    tab, scheme, method,
):
    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    response = page.goto(base + "/compounds", wait_until="networkidle")
    assert response is not None and response.status == 200
    # POST is a declared write. Other methods may be unimplemented; 405
    # is acceptable for those and is NOT counted as CSRF route clearance.
    denied = page.request.fetch(
        base + "/compounds",
        method=method,
        data={"name": "QA forbidden alternate method 578"},
        max_redirects=0,
    )
    if method == "POST":
        assert denied.status == 403
    else:
        assert denied.status in (403, 405), (method, denied.status)
    assert not errors, errors


# Release 591: end-to-end PK JSON lifecycle in the already-required full
# strict Chromium browser gate. The installed service is never contacted.
@pytest.mark.parametrize("scheme", ("http", "https"))
def test_591_pk_scenario_json_lifecycle_signed_and_unsigned_rejected(tab, scheme):
    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    response = page.goto(base + "/pk", wait_until="networkidle")
    assert response is not None and response.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")

    def unsigned(method, route):
        # APIRequestContext bypasses the browser's signed fetch wrapper.
        denied = page.request.fetch(
            base + route, method=method, data="{}",
            headers={"Content-Type": "application/json"}, max_redirects=0,
        )
        assert denied.status == 403, (scheme, method, route, denied.status)

    def signed(method, route, payload, expected):
        with page.expect_response(lambda response: (
            response.request.method == method
            and urlsplit(response.url).path == route
        )) as pending:
            result = page.evaluate("""async ({method, route, payload}) => {
                const response = await fetch(route, {
                    method, headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload), credentials: 'same-origin',
                });
                return {
                    status: response.status,
                    csrf: response.headers.get('x-tracker-csrf-report'),
                    payload: await response.json(),
                };
            }""", {"method": method, "route": route, "payload": payload})
        assert result["status"] == expected, (scheme, method, route, result)
        assert result["csrf"] == "valid", (scheme, method, route, result)
        assert pending.value.request.all_headers().get("x-tracker-csrf") == token
        return result["payload"]

    # A real PK-enabled compound is required to demonstrate a successful,
    # audited scenario lifecycle, rather than just CSRF-positive 422s.
    unsigned("POST", "/pk/compounds")
    compound = signed("POST", "/pk/compounds",
                      {"name": "Testosterone Cypionate"}, 201)
    cid = compound["id"]
    assert isinstance(cid, int) and cid > 0

    unsigned("POST", "/pk/scenarios")
    # Even a genuine signed token must not authorize a cross-site origin.
    cross_site = page.request.post(
        base + "/pk/scenarios", data="{}",
        headers={
            "Content-Type": "application/json",
            "X-Tracker-CSRF": token,
            "Origin": "https://attacker.invalid",
            "Sec-Fetch-Site": "cross-site",
        }, max_redirects=0,
    )
    assert cross_site.status == 403, (scheme, cross_site.status)
    scenario_name = "QA 591 isolated " + scheme + " " + uuid4().hex[:8]
    payload = {
        "compound_id": cid, "name": scenario_name,
        "half_life_hours": 120, "absorption_half_life_hours": 24,
    }
    created = signed("POST", "/pk/scenarios", payload, 201)
    sid = created["id"]
    assert isinstance(sid, int) and sid > 0
    scenarios_url = base + "/pk/scenarios?compound_id=" + str(cid)
    saved = page.request.get(scenarios_url)
    assert saved.status == 200
    assert any(x["id"] == sid and x["name"] == scenario_name
               for x in saved.json()), saved.text()

    scenario_route = "/pk/scenarios/" + str(sid)
    unsigned("PUT", scenario_route)
    updated_name = scenario_name + " revised"
    signed("PUT", scenario_route, {**payload, "name": updated_name}, 200)
    assert any(x["id"] == sid and x["name"] == updated_name
               for x in page.request.get(scenarios_url).json())

    doses_route = scenario_route + "/doses"
    unsigned("POST", doses_route)
    dose = signed("POST", doses_route,
                  {"planned_at": "2030-01-01T12:00:00", "amount_mg": 1.5}, 201)
    did = dose["id"]
    assert isinstance(did, int) and did > 0
    dose_route = doses_route + "/" + str(did)
    unsigned("PUT", dose_route)
    signed("PUT", dose_route,
           {"planned_at": "2030-01-02T12:00:00", "amount_mg": 2.5}, 200)
    current = next(x for x in page.request.get(scenarios_url).json()
                   if x["id"] == sid)
    assert any(x["id"] == did and x["amount_mg"] == 2.5
               for x in current["doses"])

    unsigned("DELETE", dose_route)
    signed("DELETE", dose_route, {}, 200)
    current = next(x for x in page.request.get(scenarios_url).json()
                   if x["id"] == sid)
    assert current["doses"] == []

    unsigned("DELETE", scenario_route)
    signed("DELETE", scenario_route, {}, 200)
    assert all(x["id"] != sid for x in page.request.get(scenarios_url).json())
    assert not errors, errors


# Release 591: the rest of the PK unsafe-route matrix is *negative only*.
# These forgery checks do not qualify signed endpoint compatibility and
# therefore do not add routes to BROWSER_WITNESS_CANDIDATES.
PK_UNSIGNED_ROUTES_591 = (
    ("POST", "/pk/what-if/multi-preview"),
    ("POST", "/pk/what-if/preview"),
    ("POST", "/pk/what-if/save"),
    ("POST", "/pk/compounds"),
    ("POST", "/pk/scenarios"),
    ("PUT", "/pk/scenarios/1"),
    ("DELETE", "/pk/scenarios/1"),
    ("POST", "/pk/scenarios/1/doses"),
    ("PUT", "/pk/scenarios/1/doses/1"),
    ("DELETE", "/pk/scenarios/1/doses/1"),
    ("POST", "/pk/workbench/1"),
    ("POST", "/pk/library/1"),
    ("DELETE", "/pk/library/1/1"),
    ("POST", "/pk/library/1/compare"),
    ("PUT", "/pk/library/1/1"),
    ("POST", "/pk/scenarios/1/doses/generate-preview"),
    ("POST", "/pk/scenarios/1/doses/create-batch"),
    ("POST", "/pk/scenarios/1/doses/delete-batch"),
    ("POST", "/pk/scenarios/1/doses/undo-delete"),
    ("POST", "/pk/scenarios/1/duplicate"),
    ("POST", "/pk/scenarios/1/staged-preview"),
    ("POST", "/pk/scenarios/1/staged-replace"),
    ("POST", "/pk/scenarios/import-preview"),
    ("POST", "/pk/scenarios/import-confirm"),
    ("POST", "/pk/scenarios/1/doses/create-batch-checked"),
    ("POST", "/pk/scenarios/1/calendar-preview"),
    ("POST", "/pk/scenarios/1/calendar-replace"),
    ("POST", "/pk/workspace/1/edit-dose"),
    ("POST", "/pk/workspace/1/transform-preview"),
    ("POST", "/pk/workspace/1/transform-apply"),
    ("POST", "/pk/workspace/1/revisions/1/restore"),
)


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_591_pk_unsafe_route_forgery_matrix_negative_only(tab, scheme):
    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    response = page.goto(base + "/pk", wait_until="networkidle")
    assert response is not None and response.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")
    assert len(PK_UNSIGNED_ROUTES_591) == 31
    for method, route in PK_UNSIGNED_ROUTES_591:
        denied = page.request.fetch(
            base + route, method=method, data="{}",
            headers={"Content-Type": "application/json"},
            max_redirects=0,
        )
        assert denied.status == 403, (scheme, method, route, denied.status)
        assert "CSRF token required" in denied.text(), (
            scheme, method, route, denied.text()[:160],
        )
    assert not errors, errors


# Release 592: representative positive PK schedule compatibility across the
# remaining high-impact workstreams. This is genuine browser fetch (not an
# HTTP-only TestClient) on the disposable strict-CSRF HTTP + HTTPS servers.
@pytest.mark.parametrize("scheme", ("http", "https"))
def test_592_pk_schedule_batch_import_calendar_and_transform_signed(tab, scheme):
    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    landing = page.goto(base + "/pk", wait_until="networkidle")
    assert landing is not None and landing.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")

    def signed(method, route, payload, expected):
        with page.expect_response(lambda response: (
            response.request.method == method
            and urlsplit(response.url).path == route
        )) as pending:
            result = page.evaluate("""async ({method, route, payload}) => {
                const response = await fetch(route, {
                    method, headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload), credentials: 'same-origin',
                });
                return {
                    status: response.status,
                    csrf: response.headers.get('x-tracker-csrf-report'),
                    body: await response.json(),
                };
            }""", {"method": method, "route": route, "payload": payload})
        assert result["status"] == expected, (scheme, method, route, result)
        assert result["csrf"] == "valid", (scheme, method, route, result)
        assert pending.value.request.all_headers().get("x-tracker-csrf") == token
        return result["body"]

    def denied(method, route):
        response = page.request.fetch(
            base + route, method=method, data="{}",
            headers={"Content-Type": "application/json"},
            max_redirects=0,
        )
        assert response.status == 403, (scheme, method, route, response.status)
        assert "CSRF token required" in response.text()

    def scenarios(cid):
        response = page.request.get(base + f"/pk/scenarios?compound_id={cid}")
        assert response.status == 200
        return response.json()

    def current(sid, cid):
        return next(x for x in scenarios(cid) if x["id"] == sid)

    compound = signed("POST", "/pk/compounds",
                      {"name": "Testosterone Cypionate"}, 201)
    cid = compound["id"]
    name = "QA 592 " + scheme + " " + uuid4().hex[:8]
    definition = {
        "compound_id": cid, "name": name,
        "half_life_hours": 120, "absorption_half_life_hours": 24,
    }
    created = signed("POST", "/pk/scenarios", definition, 201)
    sid = created["id"]
    route = f"/pk/scenarios/{sid}"
    batch = route + "/doses"
    sequence = {
        "start_at": "2030-01-01T12:00:00",
        "amount_mg": 1.5, "interval_days": 3, "count": 2,
    }

    preview_path = batch + "/generate-preview"
    denied("POST", preview_path)
    projected = signed("POST", preview_path, sequence, 200)
    assert len(projected["doses"]) == 2
    assert current(sid, cid)["doses"] == [], "Preview modified the scenario"

    create_path = batch + "/create-batch"
    denied("POST", create_path)
    assert signed("POST", create_path, sequence, 200)["created"] == 2
    saved = current(sid, cid)
    assert len(saved["doses"]) == 2
    ids = [x["id"] for x in saved["doses"]]

    state = page.request.get(base + route + "/dose-state")
    assert state.status == 200
    version = state.json()["version"]
    delete_path = batch + "/delete-batch"
    denied("POST", delete_path)
    deleted = signed("POST", delete_path, {"ids": ids, "expected_version": version}, 200)
    assert deleted["deleted"] == 2
    assert current(sid, cid)["doses"] == []

    undo_path = batch + "/undo-delete"
    denied("POST", undo_path)
    restored = signed("POST", undo_path, {
        "audit_id": deleted["audit_id"], "expected_version": deleted["version"],
    }, 200)
    assert restored["restored"] == 2
    assert len(current(sid, cid)["doses"]) == 2

    staged_path = route + "/staged-preview"
    staged = {"start_at": "2030-02-04T12:00:00", "stages": [
        {"amount_mg": 2.0, "count": 2, "interval_days": 7},
    ]}
    denied("POST", staged_path)
    projected = signed("POST", staged_path, staged, 200)
    assert len(projected["doses"]) == 2
    before = current(sid, cid)["doses"]
    revision = page.request.get(base + route + "/revision")
    assert revision.status == 200
    replace_path = route + "/staged-replace"
    denied("POST", replace_path)
    assert signed("POST", replace_path, {
        **staged, "expected_version": revision.json()["version"],
    }, 200)["replaced"] == 2
    after = current(sid, cid)["doses"]
    assert after != before
    assert [x["amount_mg"] for x in after] == [2.0, 2.0]

    calendar = {
        "start": "2030-03-04", "end": "2030-03-11",
        "weekdays": [0], "local_time": "12:00:00",
        "amount_mg": 3.0, "timezone_name": "America/New_York",
    }
    calendar_path = route + "/calendar-preview"
    denied("POST", calendar_path)
    projected = signed("POST", calendar_path, calendar, 200)
    assert len(projected["doses"]) == 2 and not projected["warnings"]
    revision = page.request.get(base + route + "/revision")
    assert revision.status == 200
    replace_path = route + "/calendar-replace"
    denied("POST", replace_path)
    assert signed("POST", replace_path, {
        **calendar, "expected_version": revision.json()["version"],
    }, 200)["replaced"] == 2
    assert [x["amount_mg"] for x in current(sid, cid)["doses"]] == [3.0, 3.0]

    revision = page.request.get(base + route + "/revision")
    assert revision.status == 200
    transformation = {
        "shift_hours": 24, "amount_multiplier": 2,
        "expected_version": revision.json()["version"],
    }
    transform_path = f"/pk/workspace/{sid}/transform-preview"
    denied("POST", transform_path)
    projected = signed("POST", transform_path, transformation, 200)
    assert len(projected["doses"]) == 2 and projected["saved"] is False
    assert [x["amount_mg"] for x in current(sid, cid)["doses"]] == [3.0, 3.0]

    apply_path = f"/pk/workspace/{sid}/transform-apply"
    denied("POST", apply_path)
    applied = signed("POST", apply_path, transformation, 200)
    assert applied["updated"] == 2
    assert [x["amount_mg"] for x in current(sid, cid)["doses"]] == [6.0, 6.0]

    duplicate_path = route + "/duplicate"
    denied("POST", duplicate_path)
    copied = signed("POST", duplicate_path, {}, 201)
    copy_id = copied["id"]
    assert copy_id != sid
    assert [x["amount_mg"] for x in current(copy_id, cid)["doses"]] == [6.0, 6.0]

    template = {
        "format": "tracker-pk-scenario-template-v1",
        "compound_id": cid, "compound_name": "Testosterone Cypionate",
        "name": name + " imported", "half_life_hours": 120,
        "absorption_half_life_hours": 24,
        "doses": [{"planned_at": "2030-04-01T12:00:00", "amount_mg": 4.0}],
    }
    import_path = "/pk/scenarios/import-preview"
    denied("POST", import_path)
    result = signed("POST", import_path, template, 200)
    assert result["count"] == 1 and result["compound"] == "Testosterone Cypionate"
    confirm_path = "/pk/scenarios/import-confirm"
    denied("POST", confirm_path)
    result = signed("POST", confirm_path, template, 201)
    imported_id = result["id"]
    assert result["count"] == 1
    assert [x["amount_mg"] for x in current(imported_id, cid)["doses"]] == [4.0]

    for candidate in (imported_id, copy_id, sid):
        delete_path = f"/pk/scenarios/{candidate}"
        denied("DELETE", delete_path)
        signed("DELETE", delete_path, {}, 200)
    assert not any(x["id"] in (sid, copy_id, imported_id)
                   for x in scenarios(cid))
    assert not errors, errors


# Release 593: signed, persistence-checked PK guarded edits and historical
# restoration. All writes target the disposable strict-CSRF browser database.
@pytest.mark.parametrize("scheme", ("http", "https"))
def test_593_pk_checked_batch_guarded_edit_and_revision_restore(tab, scheme):
    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    landed = page.goto(base + "/pk", wait_until="networkidle")
    assert landed is not None and landed.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")

    def signed(method, path, payload, expected=200, extra_headers=None):
        with page.expect_response(lambda response: (
            response.request.method == method
            and urlsplit(response.url).path == path
        )) as pending:
            result = page.evaluate("""async ({method,path,payload,headers}) => {
                const response = await fetch(path, {
                    method, credentials: 'same-origin',
                    headers: {'Content-Type':'application/json', ...headers},
                    body:JSON.stringify(payload)
                });
                return {status:response.status,
                    csrf:response.headers.get('x-tracker-csrf-report'),
                    data:await response.json()};
            }""", {"method":method, "path":path, "payload":payload,
                    "headers":extra_headers or {}})
        assert result["status"] == expected, (method,path,result)
        assert result["csrf"] == "valid", (method,path,result)
        assert pending.value.request.all_headers().get("x-tracker-csrf") == token
        return result["data"]

    def denied(method, path):
        result = page.request.fetch(
            base + path, method=method, data="{}",
            headers={"Content-Type":"application/json"},
            max_redirects=0)
        assert result.status == 403, (scheme,method,path,result.status)

    compound = signed("POST", "/pk/compounds",
                      {"name":"Testosterone Cypionate"}, 201)
    cid = compound["id"]
    name = "QA guarded 593 " + scheme + " " + uuid4().hex[:8]
    created = signed("POST","/pk/scenarios",{
        "compound_id":cid, "name":name,
        "half_life_hours":120, "absorption_half_life_hours":24
    },201)
    sid = created["id"]
    base_path = f"/pk/scenarios/{sid}"
    listing = base + f"/pk/scenarios?compound_id={cid}"

    def saved():
        response = page.request.get(listing)
        assert response.status == 200
        return next(row for row in response.json() if row["id"] == sid)

    def revision():
        response = page.request.get(base + base_path + "/revision")
        assert response.status == 200
        return response.json()["version"]

    checked = base_path + "/doses/create-batch-checked"
    denied("POST", checked)
    created_batch = signed("POST",checked,{
        "start_at":"2030-05-01T12:00:00", "amount_mg":1.0,
        "interval_days":7, "count":2
    },200,{"X-PK-Expected-Version":revision()})
    assert created_batch["created"] == 2
    assert len(saved()["doses"]) == 2
    first = saved()["doses"][0]
    edit = f"/pk/workspace/{sid}/edit-dose"
    denied("POST",edit)
    updated = signed("POST",edit,{
        "dose_id":first["id"],"planned_at":"2030-05-02T12:00:00",
        "amount_mg":5.0,"expected_version":revision()
    })
    assert updated["ok"] is True
    assert any(d["amount_mg"] == 5.0 for d in saved()["doses"])

    history_path = f"/pk/workspace/{sid}/revisions"
    history = page.request.get(base + history_path)
    assert history.status == 200
    eligible = [h for h in history.json()
                if h["restorable"] and h["action"] == "bulk_create"]
    assert eligible, history.text()
    audit_id = eligible[0]["id"]
    preview_path = history_path + f"/{audit_id}/preview"
    preview = page.request.get(base + preview_path)
    assert preview.status == 200
    assert preview.json()["restorable"] is True
    restore_path = history_path + f"/{audit_id}/restore"
    denied("POST",restore_path)
    restored = signed("POST",restore_path,{"expected_version":revision()})
    assert restored["audit_source"] == audit_id
    assert any(d["amount_mg"] == 1.0 for d in saved()["doses"])
    assert not any(d["amount_mg"] == 5.0 for d in saved()["doses"])
    signed("DELETE",base_path,{},200)
    assert not errors, errors


# Release 593: stateless what-if previews and save, with persisted PK scenario.
@pytest.mark.parametrize("scheme", ("http", "https"))
def test_593_pk_what_if_preview_multi_and_save(tab, scheme):
    from datetime import datetime, timedelta
    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    landing = page.goto(base + "/pk", wait_until="networkidle")
    assert landing is not None and landing.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")

    def signed(path, payload, status=200):
        with page.expect_response(lambda response: (
            response.request.method == "POST"
            and urlsplit(response.url).path == path
        )) as pending:
            result = page.evaluate("""async ({path,payload}) => {
                const response = await fetch(path, {
                    method:'POST',credentials:'same-origin',
                    headers:{'Content-Type':'application/json'},
                    body:JSON.stringify(payload)
                });
                return {status:response.status,
                    csrf:response.headers.get('x-tracker-csrf-report'),
                    data:await response.json()};
            }""",{"path":path,"payload":payload})
        assert result["status"] == status, (path,result)
        assert result["csrf"] == "valid"
        assert pending.value.request.all_headers().get("x-tracker-csrf") == token
        return result["data"]

    def denied(path):
        r = page.request.post(base+path, data="{}",
                              headers={"Content-Type":"application/json"},
                              max_redirects=0)
        assert r.status == 403, (path,r.status)

    cid = signed("/pk/compounds",
                 {"name":"Testosterone Cypionate"},201)["id"]
    schedule = {
        "compound_id":cid,"name":"QA hypothetical 593 "+uuid4().hex[:8],
        "start_at":(datetime.now()+timedelta(days=7)).replace(microsecond=0).isoformat(),
        "interval_days":3,
        "duration_days":21,"offset_days":0,
        "stages":[{"week":1,"amount_mg":1.0,"interval_days":3}],
        "half_life_hours":120,"absorption_half_life_hours":24
    }
    preview_path = "/pk/what-if/preview"
    denied(preview_path)
    preview = signed(preview_path,schedule)
    assert preview["planned_doses"] > 0

    multi_path = "/pk/what-if/multi-preview"
    denied(multi_path)
    multi = signed(multi_path,{"schedules":[schedule]})
    assert len(multi["series"]) == 1
    assert multi["series"][0]["dose_count"] > 0

    save_path = "/pk/what-if/save"
    denied(save_path)
    created = signed(save_path,schedule,201)
    assert created["planned_doses"] > 0
    sid = created["id"]
    scenarios = page.request.get(base+f"/pk/scenarios?compound_id={cid}")
    assert scenarios.status == 200
    assert any(x["id"] == sid for x in scenarios.json())
    removed = page.evaluate("""async id => {
        const r = await fetch('/pk/scenarios/'+id, {method:'DELETE'});
        return {status:r.status,csrf:r.headers.get('x-tracker-csrf-report')};
    }""",sid)
    assert removed == {"status":200,"csrf":"valid"}
    assert not errors, errors


# Release 593: saved-protocol experiment library over real signed Chromium.
# A purpose-built Protocol and ProtocolItem live only in the isolated
# /tmp/tracker-browser-qa.* SQLite database, never the installed app.
@pytest.mark.parametrize("scheme", ("http", "https"))
def test_593_pk_workbench_and_experiment_library_signed(tab, scheme):
    from datetime import date
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import Session
    from app.models import Protocol, ProtocolItem

    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    assert DATA.name == "data" and DATA.parent.parent == Path("/tmp").resolve()
    assert re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
    path = (DATA / "tracker.db").resolve()
    assert path.parent == DATA and path.is_file() and not path.is_symlink()
    landed = page.goto(base + "/pk", wait_until="networkidle")
    assert landed is not None and landed.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")

    def signed(method, route, payload, status=200):
        with page.expect_response(lambda response: (
            response.request.method == method
            and urlsplit(response.url).path == route
        )) as pending:
            result = page.evaluate("""async ({method,route,payload}) => {
                const response=await fetch(route,{
                    method,credentials:'same-origin',
                    headers:{'Content-Type':'application/json'},
                    body:JSON.stringify(payload)
                });
                return {status:response.status,
                    csrf:response.headers.get('x-tracker-csrf-report'),
                    data:await response.json()};
            }""",{"method":method,"route":route,"payload":payload})
        assert result["status"] == status, (scheme,method,route,result)
        assert result["csrf"] == "valid", (method,route,result)
        assert pending.value.request.all_headers().get("x-tracker-csrf") == token
        return result["data"]

    def denied(method,route):
        response=page.request.fetch(
            base+route,method=method,data="{}",
            headers={"Content-Type":"application/json"},
            max_redirects=0)
        assert response.status == 403, (method,route,response.status)

    compound=signed("POST","/pk/compounds",
                    {"name":"Testosterone Cypionate"},201)
    cid=compound["id"]

    engine=create_engine(f"sqlite:///{path}",
                         connect_args={"check_same_thread":False})
    @event.listens_for(engine,"connect")
    def pragmas(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")
    try:
        with Session(engine) as db:
            protocol_name="QA experiment 593 "+uuid4().hex[:8]
            protocol=Protocol(
                name=protocol_name,
                start_date=date(2030,1,1),is_active=True,
                horizon_weeks=12)
            db.add(protocol)
            db.flush()
            pid=protocol.id
            db.add(ProtocolItem(
                protocol_id=pid,compound_id=cid,position=0,
                amount_value=2.0,amount_unit="mg",
                freq_count=1,freq_period="week",
                start_week=1,dose_days="",dose_time="12:00"))
            db.commit()
        assert pid > 0
        workbench=f"/pk/workbench/{pid}"
        settings={"compound_id":cid,"horizon_days":28}
        denied("POST",workbench)
        output=signed("POST",workbench,settings)
        assert output["protocol"] == protocol_name

        library=f"/pk/library/{pid}"
        def listing():
            response=page.request.get(base+library)
            assert response.status == 200
            return response.json()

        data={"name":"QA saved 593 A "+uuid4().hex[:8],
              "notes":"initial","settings":settings}
        denied("POST",library)
        first=signed("POST",library,data)
        first_id=first["id"]
        assert re.fullmatch(r"[0-9a-f]{32}",first_id)
        assert any(x["id"] == first_id for x in listing())

        another=signed("POST",library,{**data,"name":data["name"]+" B"})
        second_id=another["id"]
        assert second_id != first_id

        revise=f"{library}/{first_id}"
        denied("PUT",revise)
        changed=signed("PUT",revise,{**data,"name":data["name"]+" revised"})
        assert changed["name"] == data["name"]+" revised"
        saved=next(x for x in listing() if x["id"] == first_id)
        assert len(saved["revisions"]) == 1

        compare=library+"/compare"
        denied("POST",compare)
        result=signed("POST",compare,{"ids":[first_id,second_id]})
        assert len(result["experiments"]) == 2

        for ident in (first_id,second_id):
            delete=f"{library}/{ident}"
            denied("DELETE",delete)
            assert signed("DELETE",delete,{})["ok"] is True
        assert listing() == []
        assert not errors, errors
    finally:
        engine.dispose()


# Release 594: guarded signed form fetch and persisted food / vendor
# mutations. Both HTTP and HTTPS use the isolated strict QA database.
@pytest.mark.parametrize("scheme", ("http", "https"))
def test_594_food_vendor_signed_forms_and_unsigned_denial(tab, scheme):
    import sqlite3
    from datetime import date

    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    assert DATA.parent.parent == Path("/tmp").resolve()
    assert re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
    database = (DATA / "tracker.db").resolve()
    assert database.parent == DATA and database.is_file() and not database.is_symlink()

    def count(sql, params=()):
        with sqlite3.connect(database) as connection:
            return connection.execute(sql, params).fetchone()[0]

    def signed(route, fields, expected=303, extra_headers=None):
        with page.expect_response(lambda response: (
            response.request.method == "POST"
            and urlsplit(response.url).path == route
        )) as pending:
            result = page.evaluate("""async ({route,fields,headers}) => {
                const body = new URLSearchParams(fields);
                const response = await fetch(route, {
                    method:'POST',credentials:'same-origin',
                    headers:{'Content-Type':'application/x-www-form-urlencoded',...headers},
                    body,
                });
                return {status:response.status,url:response.url};
            }""",{"route":route,"fields":fields,"headers":extra_headers or {}})
        response = pending.value
        assert response.status == expected, (scheme, route, response.status)
        assert response.headers.get("x-tracker-csrf-report") == "valid", (
            scheme, route, response.headers
        )
        assert response.request.all_headers().get("x-tracker-csrf") == token
        assert result["status"] == 200, (scheme,route,result)
        return response

    def unsigned(route, fields):
        response=page.request.post(base+route,data=fields,max_redirects=0)
        assert response.status == 403, (scheme,route,response.status)

    day = date.today().isoformat()
    landing = page.goto(base+"/food?day="+day, wait_until="networkidle")
    assert landing is not None and landing.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")

    # Water addition / deletion verify the same stored row rather than merely
    # accepting a CSRF-positive POST.
    water="/food/water"
    unsigned(water,{"day":day,"ounces":"8"})
    signed(water,{"day":day,"ounces":"8"})
    water_id=count("SELECT max(id) FROM tracker_water_entries WHERE logged_on=?",(day,))
    assert isinstance(water_id,int)
    assert count("SELECT ounces FROM tracker_water_entries WHERE id=?",(water_id,)) == 8
    delete_water=f"/food/water/{water_id}/delete"
    unsigned(delete_water,{"day":day})
    signed(delete_water,{"day":day})
    assert count("SELECT count(*) FROM tracker_water_entries WHERE id=?",(water_id,)) == 0

    # Native food entry and target writes; direct SQLite reads are restricted
    # to the disposable /tmp QA database above.
    name="QA food 594 "+uuid4().hex[:8]
    food="/food/entry"
    unsigned(food,{"name":name,"day":day,"servings":"1"})
    signed(food,{"name":name,"day":day,"servings":"1",
                 "meal":"Snack","energy":"90","proteins":"10"})
    entry_id=count("""SELECT max(e.id)
        FROM tracker_food_entries e JOIN tracker_food_products p
          ON e.product_id=p.id WHERE p.name=? AND e.eaten_on=?""",(name,day))
    assert isinstance(entry_id,int)
    assert count("SELECT servings FROM tracker_food_entries WHERE id=?",(entry_id,)) == 1
    targets="/food/targets"
    unsigned(targets,{"day":day,"energy":"1800"})
    signed(targets,{"day":day,"energy":"1800","proteins":"140"})
    assert count("SELECT value FROM tracker_food_targets WHERE nutrient='energy'") == 1800
    delete_food=f"/food/entry/{entry_id}/delete"
    unsigned(delete_food,{"day":day})
    signed(delete_food,{"day":day})
    assert count("SELECT count(*) FROM tracker_food_entries WHERE id=?",(entry_id,)) == 0

    vendor="QA Vendor 594 "+uuid4().hex[:8]
    vendor_page=page.goto(base+"/vendor-prices",wait_until="networkidle")
    assert vendor_page is not None and vendor_page.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")

    shipping="/vendor-prices/shipping/save"
    fields={"vendor":vendor,"flat_shipping":"7.50",
            "free_shipping_threshold":"99.00"}
    unsigned(shipping,fields)
    signed(shipping,fields)
    rule_id=count("SELECT id FROM vendor_shipping_rules WHERE vendor=?",(vendor,))
    assert isinstance(rule_id,int)
    assert count("SELECT flat_shipping_cents FROM vendor_shipping_rules WHERE id=?",(rule_id,)) == 750

    manual="/vendor-prices/manual"
    item="QA offer "+uuid4().hex[:8]
    details={"vendor":vendor,"item_name":item,"content_amount":"10",
             "content_unit":"mg","package_type":"vial",
             "package_price":"12.50"}
    unsigned(manual,details)
    signed(manual,details)
    entry_id=count("SELECT max(id) FROM vendor_price_entries WHERE item_name=?",(item,))
    assert isinstance(entry_id,int)
    assert count("SELECT total_price_cents FROM vendor_price_entries WHERE id=?",(entry_id,)) == 1250

    edit=f"/vendor-prices/entries/{entry_id}/edit"
    edit_data={"vendor":vendor,"item_name":item+" revised",
               "content_amount":"10","content_unit":"mg",
               "package":"vial","vial_count":"1","total_price":"13.50"}
    unsigned(edit,edit_data)
    signed(edit,edit_data)
    assert count("SELECT total_price_cents FROM vendor_price_entries WHERE id=?",(entry_id,)) == 1350

    delete_entry=f"/vendor-prices/entries/{entry_id}/delete"
    unsigned(delete_entry,{})
    signed(delete_entry,{})
    assert count("SELECT count(*) FROM vendor_price_entries WHERE id=?",(entry_id,)) == 0

    delete_rule=f"/vendor-prices/shipping/{rule_id}/delete"
    unsigned(delete_rule,{})
    signed(delete_rule,{})
    assert count("SELECT count(*) FROM vendor_shipping_rules WHERE id=?",(rule_id,)) == 0
    assert not errors, errors


# Release 595: full positive signed food lifecycle and vendor-sheet edits.
# Both transport variants operate only on the disposable browser QA database.
@pytest.mark.parametrize("scheme", ("http", "https"))
def test_595_food_templates_corrections_and_vendor_sheets(tab, scheme):
    import sqlite3
    from datetime import date

    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    assert DATA.name == "data" and DATA.parent.parent == Path("/tmp").resolve()
    assert re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
    database = (DATA / "tracker.db").resolve()
    assert database.parent == DATA and database.is_file() and not database.is_symlink()

    def query(sql, params=()):
        with sqlite3.connect(database) as connection:
            return connection.execute(sql, params).fetchone()

    def signed(route, fields):
        with page.expect_response(lambda response: (
            response.request.method == "POST"
            and urlsplit(response.url).path == route
        )) as pending:
            result = page.evaluate("""async ({route,fields}) => {
                const response = await fetch(route, {
                    method:'POST',credentials:'same-origin',
                    headers:{'Content-Type':'application/x-www-form-urlencoded'},
                    body:new URLSearchParams(fields),
                });
                return {status:response.status};
            }""",{"route":route,"fields":fields})
        response = pending.value
        assert response.status == 303, (scheme,route,response.status)
        assert response.headers.get("x-tracker-csrf-report") == "valid"
        assert response.request.all_headers().get("x-tracker-csrf") == token
        assert result["status"] == 200, (scheme,route,result)

    def unsigned(route, fields):
        response = page.request.post(base+route,data=fields,max_redirects=0)
        assert response.status == 403, (scheme,route,response.status)

    day = date.today().isoformat()
    landing=page.goto(base+"/food?day="+day,wait_until="networkidle")
    assert landing is not None and landing.status == 200
    token=page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")

    name="QA food 595 "+uuid4().hex[:8]
    create="/food/entry"
    signed(create,{"name":name,"day":day,"servings":"1",
                   "meal":"Lunch","energy":"100","proteins":"8",
                   "serving_description":"1 serving"})
    product = query("""SELECT e.id,e.product_id FROM tracker_food_entries e
      JOIN tracker_food_products p ON p.id=e.product_id
      WHERE p.name=? AND e.eaten_on=?""",(name,day))
    assert product is not None
    entry_id,product_id=product

    edit=f"/food/entry/{entry_id}/edit"
    change={"day":day,"original_day":day,"servings":"2","meal":"Lunch"}
    unsigned(edit,change)
    signed(edit,change)
    assert query("SELECT servings,meal FROM tracker_food_entries WHERE id=?",
                 (entry_id,)) == (2.0,"Lunch")

    nutrition=f"/food/entry/{entry_id}/nutrition"
    revised={"day":day,"name":name+" corrected","serving_description":"1 serving",
             "energy":"135","proteins":"11"}
    unsigned(nutrition,revised)
    signed(nutrition,revised)
    revised_id=query("SELECT product_id FROM tracker_food_entries WHERE id=?",
                     (entry_id,))[0]
    assert revised_id != product_id
    assert query("SELECT name FROM tracker_food_products WHERE id=?",(product_id,))[0] == name
    assert query("SELECT name FROM tracker_food_products WHERE id=?",(revised_id,))[0] == name+" corrected"

    favorite=f"/food/favorite/{revised_id}"
    unsigned(favorite,{"day":day})
    signed(favorite,{"day":day})
    assert query("SELECT product_id FROM tracker_food_favorites WHERE product_id=?",
                 (revised_id,)) == (revised_id,)

    quick=f"/food/quick/{revised_id}"
    unsigned(quick,{"day":day,"servings":"1","meal":"Lunch"})
    before=query("SELECT count(*) FROM tracker_food_entries WHERE product_id=? AND eaten_on=?",
                 (revised_id,day))[0]
    signed(quick,{"day":day,"servings":"1","meal":"Lunch"})
    assert query("SELECT count(*) FROM tracker_food_entries WHERE product_id=? AND eaten_on=?",
                 (revised_id,day))[0] == before+1

    template="/food/template/save"
    template_name="QA meal 595 "+uuid4().hex[:8]
    form={"day":day,"meal":"Lunch","name":template_name}
    unsigned(template,form)
    signed(template,form)
    tid=query("SELECT id FROM tracker_food_meal_templates WHERE name=?",
              (template_name,))[0]
    assert query("SELECT count(*) FROM tracker_food_meal_template_items WHERE template_id=?",
                 (tid,))[0] >= 1

    rename=f"/food/template/{tid}/rename"
    unsigned(rename,{"day":day,"name":template_name+" revised"})
    signed(rename,{"day":day,"name":template_name+" revised"})
    assert query("SELECT name FROM tracker_food_meal_templates WHERE id=?",
                 (tid,))[0] == template_name+" revised"

    log=f"/food/template/{tid}/log"
    unsigned(log,{"day":day})
    before=query("SELECT count(*) FROM tracker_food_entries WHERE eaten_on=?",(day,))[0]
    signed(log,{"day":day})
    assert query("SELECT count(*) FROM tracker_food_entries WHERE eaten_on=?",(day,))[0] > before

    delete=f"/food/template/{tid}/delete"
    unsigned(delete,{"day":day})
    signed(delete,{"day":day})
    assert query("SELECT count(*) FROM tracker_food_meal_templates WHERE id=?",(tid,))[0] == 0
    assert query("SELECT count(*) FROM tracker_food_entries WHERE eaten_on=?",(day,))[0] > before

    vendor_page=page.goto(base+"/vendor-prices",wait_until="networkidle")
    assert vendor_page is not None and vendor_page.status == 200
    token=page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")

    vendor="QA sheet 595 "+uuid4().hex[:8]
    sheet_name="QA import 595"
    review="Item\tStrength\tPackage\tVials\tTotal USD\nQA Test Item\t10 mg/vial\tvial\t1\t14.50\n"
    save="/vendor-prices/save"
    data={"vendor":vendor,"sheet_name":sheet_name,"review_text":review}
    unsigned(save,data)
    signed(save,data)
    sheet=query("SELECT id FROM vendor_price_sheets WHERE vendor=? AND name=?",
                (vendor,sheet_name))
    assert sheet is not None
    sid=sheet[0]
    assert query("SELECT total_price_cents FROM vendor_price_entries WHERE sheet_id=?",
                 (sid,))[0] == 1450

    delete_sheet=f"/vendor-prices/{sid}/delete"
    unsigned(delete_sheet,{})
    signed(delete_sheet,{})
    assert query("SELECT count(*) FROM vendor_price_sheets WHERE id=?",(sid,))[0] == 0
    assert query("SELECT count(*) FROM vendor_price_entries WHERE sheet_id=?",(sid,))[0] == 0
    assert not errors, errors


# Release 596: signed native multipart vendor-price archive and CSV import
# workflows, with persisted-byte verification in the disposable database.
@pytest.mark.parametrize("scheme", ("http", "https"))
def test_596_vendor_multipart_and_csv_roundtrip_signed(tab, scheme):
    import sqlite3

    page, errors = tab
    base = URL if scheme == "http" else HTTPS_URL
    assert DATA.name == "data" and DATA.parent.parent == Path("/tmp").resolve()
    assert re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
    database = (DATA / "tracker.db").resolve()
    assert database.parent == DATA and database.is_file() and not database.is_symlink()

    def query(sql, params=()):
        with sqlite3.connect(database) as connection:
            return connection.execute(sql, params).fetchone()

    landing = page.goto(base + "/vendor-prices", wait_until="networkidle")
    assert landing is not None and landing.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")
    vendor = "QA csv 596 " + uuid4().hex[:8]

    def signed(route, fields, status=303, *, upload=None):
        # Real browser fetch wrapper must sign both URL-encoded and multipart
        # requests. Capture the original POST, not its eventual redirect.
        with page.expect_response(lambda response: (
            response.request.method == "POST"
            and urlsplit(response.url).path == route
        )) as pending:
            result = page.evaluate("""async ({route,fields,upload}) => {
                let body, headers = {};
                if (upload) {
                    body = new FormData();
                    for (const [key,value] of Object.entries(fields))
                        body.append(key,value);
                    body.append('upload',new File([upload.content],
                        upload.filename,{type:upload.mimeType}));
                } else {
                    body = new URLSearchParams(fields);
                    headers['Content-Type']='application/x-www-form-urlencoded';
                }
                const response=await fetch(route,{
                    method:'POST',credentials:'same-origin',headers,body
                });
                return {status:response.status,text:(await response.text()).slice(0,60000)};
            }""", {"route":route,"fields":fields,"upload":upload})
        response = pending.value
        assert response.status == status, (scheme,route,response.status)
        assert response.headers.get("x-tracker-csrf-report") == "valid", (
            scheme,route,response.headers
        )
        assert response.request.all_headers().get("x-tracker-csrf") == token
        assert result["status"] == 200, (scheme,route,result["status"])
        return result["text"]

    def denied_form(route, fields):
        response = page.request.post(base+route,data=fields,max_redirects=0)
        assert response.status == 403, (scheme,route,response.status)

    def denied_upload(route, fields, content, filename="qa.csv"):
        payload = dict(fields)
        payload["upload"] = {
            "name":filename,"mimeType":"text/csv",
            "buffer":content.encode("utf-8")
        }
        response=page.request.post(base+route,multipart=payload,max_redirects=0)
        assert response.status == 403, (scheme,route,response.status)

    csv_text = ("vendor,item_name,content_amount,content_unit,package_type,"
                "package_price,product_url\n"
                f"{vendor},QA structured item,10,mg,vial,12.50,\n")
    upload = {"filename":"qa-596.csv","mimeType":"text/csv","content":csv_text}

    archive="/vendor-prices/attachments/upload"
    fields={"vendor":vendor,"title":"Original source evidence 596"}
    denied_upload(archive,fields,csv_text)
    signed(archive,fields,upload=upload)
    row=query("""SELECT id,filename,content FROM vendor_price_attachments
        WHERE vendor=? ORDER BY id DESC LIMIT 1""",(vendor,))
    assert row is not None
    attachment_id, filename, saved_bytes = row
    assert filename == "qa-596.csv" and saved_bytes == csv_text.encode()
    download=page.request.get(base+f"/vendor-prices/attachments/{attachment_id}/download")
    assert download.status == 200
    assert download.body() == saved_bytes
    assert download.headers.get("x-content-type-options") == "nosniff"

    attachment_delete=f"/vendor-prices/attachments/{attachment_id}/delete"
    denied_form(attachment_delete,{})
    signed(attachment_delete,{})
    assert query("SELECT count(*) FROM vendor_price_attachments WHERE id=?",
                 (attachment_id,))[0] == 0

    items_preview="/vendor-prices/items-csv/preview"
    denied_upload(items_preview,{},csv_text)
    preview_html=signed(items_preview,{},status=200,upload=upload)
    assert "QA structured item" in preview_html
    assert query("SELECT count(*) FROM vendor_price_entries WHERE item_name=?",
                 ("QA structured item",))[0] == 0

    items_save="/vendor-prices/items-csv/save"
    review=("vendor\titem_name\tcontent_amount\tcontent_unit\tpackage_type"
            "\tpackage_price\tproduct_url\n"
            f"{vendor}\tQA structured item\t10\tmg\tvial\t12.50\t\n")
    denied_form(items_save,{"review_text":review})
    signed(items_save,{"review_text":review})
    structured=query("""SELECT e.id,e.total_price_cents,e.vial_count
      FROM vendor_price_entries e JOIN vendor_price_sheets s ON e.sheet_id=s.id
      WHERE s.vendor=? AND e.item_name=?""",(vendor,"QA structured item"))
    assert structured is not None and structured[1:] == (1250,1)

    bulk_preview="/vendor-prices/bulk/preview"
    bulk=("id,vendor,item_name,content_amount,content_unit,package,vial_count,"
          "total_price,product_url\n"
          f",{vendor},QA bulk new 596,15,mg,vial,1,19.75,\n")
    denied_upload(bulk_preview,{},bulk)
    bulk_html=signed(bulk_preview,{},status=200,upload={
        "filename":"qa-596-bulk.csv","mimeType":"text/csv","content":bulk})
    assert "QA bulk new 596" in bulk_html
    assert query("SELECT count(*) FROM vendor_price_entries WHERE item_name=?",
                 ("QA bulk new 596",))[0] == 0

    bulk_save="/vendor-prices/bulk/save"
    denied_form(bulk_save,{"review_text":bulk})
    signed(bulk_save,{"review_text":bulk})
    assert query("""SELECT e.total_price_cents FROM vendor_price_entries e
        JOIN vendor_price_sheets s ON s.id=e.sheet_id
        WHERE s.vendor=? AND e.item_name=?""",
        (vendor,"QA bulk new 596")) == (1975,)

    legacy_preview="/vendor-prices/preview"
    legacy_text="QA Legacy Item,10 mg/vial,vial,1,24.00\n"
    denied_upload(legacy_preview,{"vendor":vendor},legacy_text)
    legacy_html=signed(legacy_preview,{"vendor":vendor,"sheet_name":"QA Legacy 596"},
                       status=200,upload={
                           "filename":"qa-596-legacy.csv",
                           "mimeType":"text/csv","content":legacy_text})
    assert "QA Legacy Item" in legacy_html
    assert query("SELECT count(*) FROM vendor_price_sheets WHERE vendor=? AND name=?",
                 (vendor,"QA Legacy 596"))[0] == 0
    assert not errors, errors
