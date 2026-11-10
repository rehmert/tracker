"""Release 537: authenticated smoke diagnostic reliability."""

import importlib.util
from pathlib import Path

import pytest
from urllib.error import HTTPError, URLError


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke537", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeOpener:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = []

    def open(self, request, timeout=6):
        self.calls.append((request.full_url, timeout))
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class Response:
    status = 200

    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.content


def test_successful_fetch537(smoke):
    opener = FakeOpener([Response(b"page")])
    content = smoke.fetch_page(
        opener, "http://127.0.0.1:8765",
        "/vitals", {},
    )
    assert content == b"page"


def test_http_failure_keeps_actual_status537(smoke):
    error = HTTPError(
        "http://127.0.0.1:8765/vitals",
        503, "Unavailable", {}, None,
    )
    opener = FakeOpener([error])

    with pytest.raises(
        smoke.SmokeRequestError, match="HTTP 503"
    ):
        smoke.fetch_page(
            opener, "http://127.0.0.1:8765",
            "/vitals", {},
        )


def test_transport_failure_is_not_http_zero537(smoke):
    opener = FakeOpener([
        URLError(ConnectionRefusedError("connection refused"))
    ])

    with pytest.raises(
        smoke.SmokeRequestError,
        match="TRANSPORT ConnectionRefusedError",
    ):
        smoke.fetch_page(
            opener, "http://127.0.0.1:8765",
            "/vitals", {},
        )


def test_timeout_is_reported537(smoke):
    opener = FakeOpener([TimeoutError("timed out")])

    with pytest.raises(
        smoke.SmokeRequestError,
        match="TRANSPORT TimeoutError",
    ):
        smoke.fetch_page(
            opener, "http://127.0.0.1:8765",
            "/labs", {},
        )


def test_readiness_waits_for_dashboard537(
    smoke, monkeypatch,
):
    opener = FakeOpener([
        Response(b'{"ok":true}'),
        HTTPError(
            "http://127.0.0.1:8765/",
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
        opener, "http://127.0.0.1:8765", {}
    )

    assert b"<title>" in result
    assert len(opener.calls) == 4
    assert sleeps == [1]


def test_readiness_requires_authenticated_dashboard537(
    smoke, monkeypatch,
):
    opener = FakeOpener([
        Response(b'{"ok":true}'),
        Response(b"<title>Tracker</title>"),
    ])

    result = smoke.wait_for_authenticated_readiness(
        opener, "http://127.0.0.1:8765", {}
    )
    assert result.startswith(b"<title>")


def test_readiness_timeout_preserves_failure537(
    smoke, monkeypatch,
):
    opener = FakeOpener([
        URLError(ConnectionRefusedError("refused"))
    ])

    clock = iter([0, 46])

    monkeypatch.setattr(
        smoke.time, "monotonic",
        lambda: next(clock),
    )

    with pytest.raises(
        ValueError,
        match="Authenticated readiness failed",
    ):
        smoke.wait_for_authenticated_readiness(
            opener, "http://127.0.0.1:8765", {}
        )


def test_session_lifetime_bounded537():
    source = SCRIPT.read_text()

    assert "(int(time.time()) + 600, hashed)" in source
    assert "auth.revoke(token)" in source
    assert "finally:" in source


def test_no_silent_http_zero537():
    source = SCRIPT.read_text()

    assert "status = 0" not in source
    assert "except OSError:\\n                    pass" not in source
    assert "SIDEBAR_FAILURES=" in source


def test_no_sidebar_retry537():
    source = SCRIPT.read_text()

    assert "def fetch_page(" in source
    assert "def wait_for_authenticated_readiness(" in source
    assert "for number, path in enumerate(paths, 1):" in source
    assert "time.sleep(1)" in source
