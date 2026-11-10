"""Release 542: fail-fast 401/403 diagnostics."""

import importlib.util
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke542", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Response:
    status = 200

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.body


class Opener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def open(self, request, timeout=6):
        self.calls.append(request.full_url)
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return result


def http_error(status):
    return HTTPError(
        "http://127.0.0.1:8000/",
        status,
        "Sensitive upstream error text",
        {"X-Internal-Secret": "not-for-logs"},
        None,
    )


@pytest.mark.parametrize("status", [401, 403])
def test_auth_rejection_reports_status_only542(
    smoke, status
):
    opener = Opener([http_error(status)])

    with pytest.raises(
        smoke.SmokeAuthenticationRejected,
        match=f"AUTH_REJECTED HTTP {status}",
    ) as error:
        smoke.fetch_page(
            opener,
            "http://127.0.0.1:8000",
            "/",
            {"Authorization": "Basic secret"},
        )

    assert str(error.value) == (
        f"AUTH_REJECTED HTTP {status}"
    )
    assert "secret" not in str(error.value)
    assert "Sensitive" not in str(error.value)


@pytest.mark.parametrize(
    "status,stage",
    [(401, "health"), (403, "dashboard")],
)
def test_auth_rejection_fails_without_retry542(
    smoke, monkeypatch, status, stage
):
    responses = (
        [http_error(status)]
        if stage == "health"
        else [
            Response(b'{"ok":true}'),
            http_error(status),
        ]
    )

    opener = Opener(responses)

    sleeps = []
    monkeypatch.setattr(
        smoke.time,
        "sleep",
        lambda seconds: sleeps.append(seconds),
    )

    with pytest.raises(
        ValueError,
        match=f"AUTH_REJECTED HTTP {status}",
    ):
        smoke.wait_for_authenticated_readiness(
            opener,
            "http://127.0.0.1:8000",
            {},
        )

    assert len(opener.calls) == (
        1 if stage == "health" else 2
    )
    assert sleeps == []


def test_503_remains_retryable542(
    smoke, monkeypatch
):
    opener = Opener([
        http_error(503),
        Response(b'{"ok":true}'),
        Response(b"<title>Tracker</title>"),
    ])

    sleeps = []
    monkeypatch.setattr(
        smoke.time,
        "sleep",
        lambda seconds: sleeps.append(seconds),
    )

    result = smoke.wait_for_authenticated_readiness(
        opener,
        "http://127.0.0.1:8000",
        {},
    )

    assert b"<title>" in result
    assert len(opener.calls) == 3
    assert sleeps == [1]


def test_transport_error_remains_retryable542(
    smoke, monkeypatch
):
    opener = Opener([
        URLError("connection refused"),
        Response(b'{"ok":true}'),
        Response(b"<title>Tracker</title>"),
    ])

    sleeps = []
    monkeypatch.setattr(
        smoke.time,
        "sleep",
        lambda seconds: sleeps.append(seconds),
    )

    result = smoke.wait_for_authenticated_readiness(
        opener,
        "http://127.0.0.1:8000",
        {},
    )

    assert b"<title>" in result
    assert len(opener.calls) == 3
    assert sleeps == [1]


def test_login_redirect_and_cleanup_retained542():
    source = SCRIPT.read_text()

    assert "SmokeAuthenticationRedirect" in source
    assert "SmokeAuthenticationRejected" in source
    assert "AUTH_REDIRECT HTTP" in source
    assert "AUTH_REJECTED HTTP" in source
    assert "auth.revoke(token)" in source
    assert "SIDEBAR_FAILURES=" in source
