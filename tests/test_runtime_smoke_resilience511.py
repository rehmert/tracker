"""Release 511: offline test of robust live HTTP smoke diagnostics.

All tests use fake HTTP connections. They do not contact the real tracker
service, touch live data, or incur actual retry delays.
"""
import importlib.util
from contextlib import nullcontext
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "tracker_smoke_resilient511", ROOT / "scripts/tracker-runtime-smoke.py"
)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


class Response:
    def __init__(self, status=200, body=b"ok"):
        self.status = status
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _size):
        return self.body


class Opener:
    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.calls = 0

    def open(self, _request, timeout):
        assert timeout > 0
        self.calls += 1
        result = self.sequence[min(self.calls - 1, len(self.sequence) - 1)]
        if isinstance(result, Exception):
            raise result
        return result


class Clock:
    def __init__(self):
        self.current = 0
        self.pauses = []

    def clock(self):
        return self.current

    def pause(self, seconds):
        assert seconds > 0
        self.pauses.append(seconds)
        self.current += seconds


def test_511_temporary_connection_failure_is_retried_before_false_rollback():
    fake = Opener([
        urllib.error.URLError("connection refused"),
        ConnectionResetError("socket reset"),
        Response(200, b"healthy"),
    ])
    clock = Clock()
    body = smoke.read_http_page(
        fake, "http://127.0.0.1:8000", "/calendar", {},
        clock=clock.clock, pause=clock.pause,
    )
    assert body == b"healthy"
    assert fake.calls == 3
    assert len(clock.pauses) == 2


def test_511_persistent_socket_failure_reports_its_actual_cause():
    fake = Opener([urllib.error.URLError("connection refused")])
    clock = Clock()
    with pytest.raises(smoke.TransportFailure, match="connection refused") as exc:
        smoke.read_http_page(
            fake, "http://127.0.0.1:8000", "/calendar", {},
            clock=clock.clock, pause=clock.pause,
        )
    assert "/calendar" in str(exc.value)
    assert "attempts=" in str(exc.value)
    assert fake.calls >= 2
    assert clock.current >= 4


def test_511_auth_redirect_is_not_retried_or_misreported_as_http_zero():
    fake = Opener([urllib.error.HTTPError(
        "http://127.0.0.1:8000/healthz", 303, "See Other", {}, None
    )])
    clock = Clock()
    with pytest.raises(ValueError, match="/healthz: HTTP 303"):
        smoke.read_http_page(
            fake, "http://127.0.0.1:8000", "/healthz", {},
            clock=clock.clock, pause=clock.pause,
        )
    assert fake.calls == 1
    assert not clock.pauses


def test_511_application_http_error_is_not_hidden_as_transport_outage():
    fake = Opener([Response(500, b"failure")])
    with pytest.raises(ValueError, match="HTTP 500"):
        smoke.read_http_page(
            fake, "http://127.0.0.1:8000", "/doses", {},
        )
    assert fake.calls == 1


def test_511_normal_response_is_unmodified():
    fake = Opener([Response(200, b"<title>Tracker</title>")])
    assert smoke.read_http_page(
        fake, "http://127.0.0.1:8000", "/mobile", {},
    ) == b"<title>Tracker</title>"
    assert fake.calls == 1


def test_511_live_smoke_aborts_after_consecutive_transport_failures():
    source = (ROOT / "scripts/tracker-runtime-smoke.py").read_text()
    assert "consecutive_transport_failures >= 2" in source
    assert "stopped after {checked}/{len(paths)} checks" in source
    assert "service_state()" in source
    assert "tracker-instance--{instance.lower()}" in source
    assert 'health = get("/healthz", startup=True)' in source
    assert 'dashboard = get("/")' in source
    assert "release_auth_headers(instance, settings)" in source


def test_511_full_sidebar_smoke_stops_at_outage_not_48_http_zeroes(
    tmp_path, monkeypatch
):
    env = tmp_path / "tracker.env"
    env.write_text("TRACKER_INSTANCE=PROD\\n")
    monkeypatch.setattr(
        smoke, "read_env", lambda _path: {"TRACKER_INSTANCE": "PROD"}
    )
    monkeypatch.setattr(smoke, "release_auth_headers", lambda *_: nullcontext({}))
    monkeypatch.setattr(smoke, "port_from_service", lambda: 8000)
    monkeypatch.setattr(smoke, "service_state", lambda: "ActiveState=failed")
    monkeypatch.setattr(
        smoke.urllib.request, "build_opener", lambda *args: object()
    )
    links = "".join(f'<a href="/page{i}">Page {i}</a>' for i in range(36))
    dashboard = (
        '<title>Tracker</title><nav id="app-sidebar">' +
        links + '</nav><span class="tracker-instance--prod"></span>'
    ).encode()
    calls = []

    def fake_read(_opener, _origin, path, _headers, *, startup=False):
        calls.append(path)
        if path == "/healthz":
            return b'{"ok":true}'
        if path == "/":
            return dashboard
        if path in ("/page0", "/page1"):
            return b"<title>Tracker</title>tracker-instance--prod"
        raise smoke.TransportFailure(
            f"{path}: transport ConnectionRefusedError: [Errno 111] refused"
        )

    monkeypatch.setattr(smoke, "read_http_page", fake_read)
    with pytest.raises(ValueError, match="stopped after") as exc:
        smoke.run("PROD", env)
    assert "ActiveState=failed" in str(exc.value)
    assert "/page2" in str(exc.value)
    assert "/page3" in str(exc.value)
    assert "/page4" not in calls
    assert len(calls) == 6  # health, dashboard, 2 successes, 2 failures
