"""Release 543: prevent transport-detail leakage."""

import importlib.util
from pathlib import Path
from urllib.error import URLError

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke543", SCRIPT
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


@pytest.mark.parametrize(
    "failure,expected",
    [
        (
            URLError(
                "internal-host.example:private-token"
            ),
            "TRANSPORT URLError",
        ),
        (
            URLError(
                ConnectionRefusedError(
                    "internal-host.example:private-token"
                )
            ),
            "TRANSPORT ConnectionRefusedError",
        ),
        (
            URLError(
                TimeoutError("secret-timeout-detail")
            ),
            "TRANSPORT TimeoutError",
        ),
        (
            ConnectionRefusedError(
                "internal-host.example:private-token"
            ),
            "TRANSPORT ConnectionRefusedError",
        ),
        (
            TimeoutError("secret-timeout-detail"),
            "TRANSPORT TimeoutError",
        ),
    ],
)
def test_transport_details_not_exposed543(
    smoke, failure, expected
):
    opener = Opener([failure])

    with pytest.raises(
        smoke.SmokeRequestError
    ) as error:
        smoke.fetch_page(
            opener,
            "http://127.0.0.1:8000",
            "/",
            {"Authorization": "Bearer secret"},
        )

    message = str(error.value)

    assert message == expected
    assert "private-token" not in message
    assert "internal-host" not in message
    assert "secret-timeout-detail" not in message
    assert "Bearer" not in message


@pytest.mark.parametrize(
    "failure",
    [
        URLError("hidden-connect-information"),
        URLError(
            ConnectionRefusedError(
                "hidden-connect-information"
            )
        ),
        TimeoutError("hidden-connect-information"),
    ],
)
def test_transport_readiness_retries543(
    smoke, monkeypatch, failure
):
    opener = Opener([
        failure,
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

    assert result == b"<title>Tracker</title>"
    assert len(opener.calls) == 3
    assert sleeps == [1]


def test_previous_security_behaviors_retained543():
    source = SCRIPT.read_text()

    for marker in (
        "SmokeAuthenticationRedirect",
        "SmokeAuthenticationRejected",
        "AUTH_REDIRECT HTTP",
        "AUTH_REJECTED HTTP",
        "auth.revoke(token)",
        "SIDEBAR_FAILURES=",
        "service_working_directory()",
    ):
        assert marker in source
