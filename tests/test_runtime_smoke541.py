"""Release 541: authentication redirects fail fast."""

import importlib.util
from pathlib import Path
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke541", SCRIPT
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


def redirect(path="/login?next=%2Fprivate"):
    return HTTPError(
        "http://127.0.0.1:8000/",
        303,
        "See Other",
        {"Location": path},
        None,
    )


def test_login_redirect_fails_immediately541(
    smoke, monkeypatch
):
    opener = Opener([
        Response(b'{"ok":true}'),
        redirect(),
    ])

    sleeps = []
    monkeypatch.setattr(
        smoke.time, "sleep",
        lambda seconds: sleeps.append(seconds),
    )

    with pytest.raises(
        ValueError,
        match="AUTH_REDIRECT HTTP 303 to /login",
    ) as error:
        smoke.wait_for_authenticated_readiness(
            opener, "http://127.0.0.1:8000", {}
        )

    assert len(opener.calls) == 2
    assert sleeps == []
    assert "next=" not in str(error.value)
    assert "private" not in str(error.value)


def test_external_login_redirect_reports_only_path541(smoke):
    opener = Opener([
        redirect(
            "https://example.invalid/login?secret=hidden"
        )
    ])

    with pytest.raises(
        smoke.SmokeAuthenticationRedirect,
        match="AUTH_REDIRECT HTTP 303 to /login",
    ) as error:
        smoke.fetch_page(
            opener, "http://127.0.0.1:8000", "/", {}
        )

    assert "hidden" not in str(error.value)
    assert "example.invalid" not in str(error.value)


def test_non_login_redirect_remains_http_failure541(smoke):
    opener = Opener([redirect("/maintenance")])

    with pytest.raises(
        smoke.SmokeRequestError, match="HTTP 303"
    ) as error:
        smoke.fetch_page(
            opener, "http://127.0.0.1:8000", "/", {}
        )

    assert not isinstance(
        error.value,
        smoke.SmokeAuthenticationRedirect,
    )


def test_transient_503_still_retries541(
    smoke, monkeypatch
):
    opener = Opener([
        Response(b'{"ok":true}'),
        HTTPError(
            "http://127.0.0.1:8000/",
            503, "Starting", {}, None,
        ),
        Response(b'{"ok":true}'),
        Response(b"<title>Tracker</title>"),
    ])

    sleeps = []
    monkeypatch.setattr(
        smoke.time, "sleep",
        lambda seconds: sleeps.append(seconds),
    )

    result = smoke.wait_for_authenticated_readiness(
        opener, "http://127.0.0.1:8000", {}
    )

    assert b"<title>" in result
    assert len(opener.calls) == 4
    assert sleeps == [1]


def test_session_cleanup_preserved541():
    source = SCRIPT.read_text()

    assert "auth.revoke(token)" in source
    assert "finally:" in source
    assert "AUTH_REDIRECT HTTP" in source
    assert "SIDEBAR_FAILURES=" in source
