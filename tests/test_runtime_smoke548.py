"""Release 548: reject oversized/truncated HTTP responses."""

import importlib.util
import io
from pathlib import Path
import urllib.error

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke548", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse(io.BytesIO):
    def __init__(self, content, status=200):
        super().__init__(content)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class FakeOpener:
    def __init__(self, content, status=200):
        self.content = content
        self.status = status
        self.requests = []

    def open(self, request, timeout=6):
        self.requests.append((request, timeout))
        return FakeResponse(self.content, self.status)


def fetch(smoke, content, status=200):
    opener = FakeOpener(content, status)

    result = smoke.fetch_page(
        opener,
        "http://127.0.0.1:8000",
        "/test",
        {"User-Agent": "Release548-Test"},
    )

    assert len(opener.requests) == 1
    return result


def test_small_response_accepted548(smoke):
    body = b"<title>Tracker</title>"

    assert fetch(smoke, body) == body


def test_empty_response_preserved548(smoke):
    assert fetch(smoke, b"") == b""


def test_exact_size_limit_accepted548(smoke):
    body = b"x" * smoke.MAX_RESPONSE_BYTES

    assert fetch(smoke, body) == body


def test_one_byte_over_limit_rejected548(smoke):
    body = b"x" * (smoke.MAX_RESPONSE_BYTES + 1)

    with pytest.raises(
        smoke.SmokeRequestError,
        match="response exceeding size limit",
    ):
        fetch(smoke, body)


def test_much_larger_response_rejected548(smoke):
    body = b"x" * (smoke.MAX_RESPONSE_BYTES + 10000)

    with pytest.raises(
        smoke.SmokeRequestError,
        match="response exceeding size limit",
    ):
        fetch(smoke, body)


def test_valid_title_cannot_hide_oversize548(smoke):
    prefix = (
        b'<title>Tracker</title>'
        b'<body class="tracker-instance--dev">'
    )

    body = prefix + b"x" * smoke.MAX_RESPONSE_BYTES

    with pytest.raises(
        smoke.SmokeRequestError,
        match="response exceeding size limit",
    ):
        fetch(smoke, body)


@pytest.mark.parametrize("status", [201, 404, 500, 503])
def test_non_200_status_still_rejected548(smoke, status):
    with pytest.raises(
        smoke.SmokeRequestError,
        match=rf"HTTP {status}",
    ):
        fetch(smoke, b"body", status=status)


def test_authentication_error_classification_preserved548(smoke):
    class RejectingOpener:
        def open(self, request, timeout=6):
            raise urllib.error.HTTPError(
                request.full_url,
                403,
                "Forbidden",
                {},
                None,
            )

    with pytest.raises(
        smoke.SmokeAuthenticationRejected,
        match="AUTH_REJECTED HTTP 403",
    ):
        smoke.fetch_page(
            RejectingOpener(),
            "http://127.0.0.1:8000",
            "/private",
            {},
        )


def test_response_read_is_bounded548():
    source = SCRIPT.read_text()

    assert "response.read(MAX_RESPONSE_BYTES + 1)" in source
    assert "if len(body) > MAX_RESPONSE_BYTES:" in source
    assert "response.read(3 * 1024 * 1024)" not in source


def test_prior_security_and_coverage_guards548():
    source = SCRIPT.read_text()

    for marker in (
        "validate_health_response(health)",
        "validate_dashboard_identity(dashboard, instance)",
        "validate_sidebar_coverage(paths)",
        "AUTH_REDIRECT HTTP",
        "AUTH_REJECTED HTTP",
        "auth.revoke(token)",
        "SIDEBAR_FAILURES=",
        '"TRANSPORT " + category',
    ):
        assert marker in source
