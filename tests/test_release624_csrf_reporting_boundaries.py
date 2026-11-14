"""Release 624: boundary regression tests for CSRF reporting on write requests.

These are deterministic unit tests of existing behavior, not claims that
global strict CSRF enforcement is safe or already enabled.
"""
import asyncio
from app import csrf_reporting as csrf


class Headers(dict):
    def __init__(self, values=None, repeated=()):
        super().__init__(values or {})
        self.repeated = tuple(repeated)

    def getlist(self, name):
        return list(self.repeated) if name == csrf.HEADER_NAME else []


class Request:
    def __init__(self, *, method="POST", content_type="", body=b"",
                 headers=(), cookie=None, fail_on_read=False):
        values = {"content-type": content_type, "content-length": str(len(body))}
        self.headers = Headers(values, repeated=headers)
        self.cookies = {csrf.COOKIE_NAME: cookie} if cookie else {}
        self.method = method
        self.payload = body
        self.fail_on_read = fail_on_read
        self.body_calls = 0

    async def body(self):
        self.body_calls += 1
        if self.fail_on_read:
            raise AssertionError("body must not be consumed")
        return self.payload


def status(request):
    return asyncio.run(csrf.report_status(request))


def test_624_multipart_does_not_consume_upload_stream():
    req = Request(content_type="multipart/form-data; boundary=sample",
                  fail_on_read=True)
    assert status(req) == "form-uninspected"
    assert req.body_calls == 0


def test_624_multipart_duplicate_or_empty_headers_fail_without_reading():
    for headers in (("a", "b"), ("",)):
        req = Request(content_type="multipart/form-data; boundary=x",
                      headers=headers, fail_on_read=True)
        assert status(req) == "invalid"
        assert req.body_calls == 0


def test_624_urlencoded_duplicate_tokens_not_accepted(monkeypatch):
    monkeypatch.setattr(csrf, "_verify", lambda cookie, token: "valid")
    req = Request(content_type="application/x-www-form-urlencoded",
                  body=(csrf.FIELD_NAME + "=first&" + csrf.FIELD_NAME
                        + "=second").encode())
    assert status(req) == "invalid"
    assert req.body_calls == 1


def test_624_header_precedence_does_not_fall_back_to_form(monkeypatch):
    monkeypatch.setattr(csrf, "_verify", lambda cookie, token: "valid")
    req = Request(content_type="application/x-www-form-urlencoded",
                  body=(csrf.FIELD_NAME + "=valid").encode(),
                  headers=("",))
    assert status(req) == "invalid"
    assert req.body_calls == 0


def test_624_large_urlencoded_write_remains_uninspected():
    req = Request(content_type="application/x-www-form-urlencoded",
                  body=b"x" * (csrf.MAX_INSPECT_BYTES + 1),
                  fail_on_read=True)
    assert status(req) == "form-uninspected"
    assert req.body_calls == 0


def test_624_read_only_method_skips_csrf_report_and_body():
    req = Request(method="GET", content_type="multipart/form-data",
                  fail_on_read=True)
    assert status(req) is None
    assert req.body_calls == 0


def test_624_missing_write_token_reports_missing_not_protected():
    req = Request(content_type="application/json", body=b"{}",
                  fail_on_read=True)
    assert status(req) == "missing"
    assert req.body_calls == 0
