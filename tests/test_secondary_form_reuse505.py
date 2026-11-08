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
