"""Release 505: no duplicate correction GET; preserve real CSRF/POST checks.

These tests exercise only the Release 440 test helper and deliberately avoid
patching private-worker subprocesses or production application code.
"""
from pathlib import Path

import httpx
import pytest

from scripts.secondary_integration440_support import _post_form


PAGE_PATH = "/secondary/reconcile/vials/1"
ACTION = "/secondary/reconcile/correct"
FORM = """
<form method="post" action="/secondary/reconcile/correct">
  <input type="hidden" name="csrf_token" value="csrf-505">
  <input type="hidden" name="submission_token" value="submission-505">
</form>
"""


class NoDuplicateGet:
    def __init__(self):
        self.posts = []
        self.gets = 0

    def get(self, *_args, **_kwargs):
        self.gets += 1
        raise AssertionError("Unnecessary second GET of already checked form")

    def post(self, path, *, data, follow_redirects):
        self.posts.append((path, data, follow_redirects))
        return httpx.Response(
            303, request=httpx.Request("POST", "https://tracker.test" + path)
        )


def page_response(path=PAGE_PATH, *, method="GET", status_code=200):
    return httpx.Response(
        status_code, text=FORM,
        request=httpx.Request(method, "https://tracker.test" + path),
    )


def test_505_existing_authenticated_form_can_be_posted_without_second_get():
    client = NoDuplicateGet()
    result = _post_form(
        client, PAGE_PATH, ACTION, {"vial_id": "1"}, page=page_response(),
    )
    assert result.status_code == 303
    assert client.gets == 0
    assert client.posts == [(
        ACTION,
        {
            "csrf_token": "csrf-505",
            "submission_token": "submission-505",
            "vial_id": "1",
        },
        False,
    )]


@pytest.mark.parametrize(
    ("path", "method", "status"),
    [
        ("/secondary/reconcile/vials/2", "GET", 200),
        ("/secondary/reconcile/vials/1?user_id=3", "GET", 200),
        (PAGE_PATH, "POST", 200),
        (PAGE_PATH, "GET", 403),
    ],
)
def test_505_reused_form_must_be_successful_exact_path_get(
    path, method, status
):
    client = NoDuplicateGet()
    with pytest.raises(AssertionError):
        _post_form(
            client, PAGE_PATH, ACTION, {"vial_id": "1"},
            page=page_response(path, method=method, status_code=status),
        )
    assert client.gets == 0
    assert client.posts == []


def test_505_real_workflow_still_requires_correction_snapshot_and_post():
    source = (
        Path(__file__).resolve().parent
        / "test_secondary_private_workflow440.py"
    ).read_text(encoding="utf-8")
    assert 'correction_page = client.get("/secondary/reconcile/vials/1")' in source
    assert 'assert correction_page.status_code == 200' in source
    assert 'assert "8 mg" in correction_page.text' in source
    assert '"snapshot": _hidden(correction_page.text, "snapshot")' in source
    assert 'page=correction_page' in source
    assert 'client, "/secondary/reconcile/vials/1", "/secondary/reconcile/correct"' in source
    assert '"reason": "Physical vial label verified"' in source


def test_505_dose_and_reconstitution_forms_reuse_checked_gets():
    root = Path(__file__).resolve().parent
    scenarios = (
        (
            "test_secondary_dose_write434.py",
            "def _dose_form(client, *, page=None):",
            'page = client.get("/secondary/doses/new")',
            'data = _dose_form(client, page=page)',
            '"csrf_token": _field(page.text, "csrf_token")',
            '"/secondary/doses/new", data=data, follow_redirects=False,',
            'assert page.request.url.path == "/secondary/doses/new"',
        ),
        (
            "test_secondary_reconstitution436.py",
            "def _form(client, *, page=None):",
            'page = client.get("/secondary/reconstitution")',
            'form = _form(client, page=page)',
            '"csrf_token": _field(response.text, "csrf_token")',
            '"/secondary/reconstitution", data=form, follow_redirects=False,',
            'assert response.request.url.path == "/secondary/reconstitution"',
        ),
    )
    for path, helper, first_get, reused, csrf, post, exact in scenarios:
        source = (root / path).read_text(encoding="utf-8")
        for marker in (helper, first_get, reused, csrf, post, exact):
            assert marker in source, (path, marker)
        assert 'assert not ' in source and '.request.url.query' in source


def test_505_supply_and_supply_use_pages_keep_all_security_checks():
    root = Path(__file__).resolve().parent
    supply = (root / "test_secondary_supply438.py").read_text(
        encoding="utf-8"
    )
    supply_use = (root / "test_secondary_supply_use439.py").read_text(
        encoding="utf-8"
    )
    for marker in (
        'escaped_page = client.get("/secondary/supplies")',
        'assert "&lt;img" in escaped_page.text',
        'assert \'<img src=x onerror=\' not in escaped_page.text',
        'disabled_page = client.get("/secondary/supplies")',
        'assert disabled_page.status_code == 200',
        'assert \'action="/secondary/supplies"\' not in disabled_page.text',
        'assert client.post("/secondary/supplies", data=form).status_code == 404',
    ):
        assert marker in supply, marker
    for marker in (
        'disabled_page = client.get("/secondary/supplies")',
        'assert disabled_page.status_code == 200',
        'assert \'href="/secondary/supplies/use"\' not in disabled_page.text',
        'assert client.post("/secondary/supplies/use", data=form).status_code == 404',
    ):
        assert marker in supply_use, marker
