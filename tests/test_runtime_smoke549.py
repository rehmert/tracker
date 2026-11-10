"""Release 549: stop immediately when sidebar authentication fails."""

import importlib.util
import io
from contextlib import nullcontext
from pathlib import Path
import urllib.error

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke549", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dashboard():
    links = "".join(
        f'<a href="/page-{number}">Page</a>'
        for number in range(52)
    )

    return (
        '<html><head><title>Tracker</title></head>'
        '<body class="tracker-instance--dev">'
        f'<nav id="app-sidebar">{links}</nav>'
        '</body></html>'
    ).encode()


class Response(io.BytesIO):
    def __init__(self, body, status=200):
        super().__init__(body)
        self.status = status


class Opener:
    def __init__(self, failure):
        self.failure = failure
        self.calls = []

    def open(self, request, timeout=6):
        self.calls.append(request.full_url)

        if len(self.calls) == 1:
            raise self.failure(request.full_url)

        return Response(
            b'<title>Tracker</title>'
            b'<body class="tracker-instance--dev">'
        )


def prepare(smoke, monkeypatch, opener):
    monkeypatch.setattr(
        smoke,
        "read_env",
        lambda path: {"TRACKER_INSTANCE": "DEV"},
    )

    monkeypatch.setattr(
        smoke,
        "release_auth_headers",
        lambda *args: nullcontext({}),
    )

    monkeypatch.setattr(
        smoke,
        "port_from_service",
        lambda: 8000,
    )

    monkeypatch.setattr(
        smoke,
        "wait_for_authenticated_readiness",
        lambda *args: dashboard(),
    )

    monkeypatch.setattr(
        smoke.urllib.request,
        "build_opener",
        lambda *args: opener,
    )


def http_error(code, location=None):
    def make(url):
        headers = {}
        if location is not None:
            headers["Location"] = location

        return urllib.error.HTTPError(
            url, code, "HTTP failure", headers, None
        )

    return make


@pytest.mark.parametrize("code", [401, 403])
def test_auth_rejection_stops_sidebar_immediately549(
    smoke, monkeypatch, code
):
    opener = Opener(http_error(code))
    prepare(smoke, monkeypatch, opener)

    with pytest.raises(
        ValueError,
        match=rf"Authenticated sidebar rejected: AUTH_REJECTED HTTP {code}",
    ):
        smoke.run("DEV", Path("/unused"))

    assert len(opener.calls) == 1


@pytest.mark.parametrize(
    "code",
    [301, 302, 303, 307, 308],
)
def test_login_redirect_stops_immediately549(
    smoke, monkeypatch, code
):
    opener = Opener(
        http_error(
            code,
            "/login?next=%2Fprivate&token=do-not-log",
        )
    )

    prepare(smoke, monkeypatch, opener)

    with pytest.raises(
        ValueError,
        match=rf"Authenticated sidebar rejected: AUTH_REDIRECT HTTP {code} to /login",
    ) as caught:
        smoke.run("DEV", Path("/unused"))

    assert len(opener.calls) == 1
    assert "do-not-log" not in str(caught.value)


def test_transient_http_failure_is_aggregated549(
    smoke, monkeypatch, capsys
):
    opener = Opener(http_error(503))
    prepare(smoke, monkeypatch, opener)

    with pytest.raises(
        ValueError,
        match="1/52 pages failed",
    ):
        smoke.run("DEV", Path("/unused"))

    assert len(opener.calls) == 52

    output = capsys.readouterr().out

    assert "SIDEBAR_FAILURES=1" in output
    assert "FAIL /page-0: HTTP 503" in output
    assert "PASS /page-51: HTTP 200" in output


def test_auth_exception_precedes_generic_catch549():
    source = SCRIPT.read_text()

    run_source = source[
        source.index("def run(instance, envfile):"):
    ]

    assert (
        run_source.index(
            "except (\n"
            "                SmokeAuthenticationRedirect,\n"
            "                SmokeAuthenticationRejected,"
        )
        <
        run_source.index(
            "except SmokeRequestError as error:"
        )
    )


def test_previous_safety_guards_preserved549():
    source = SCRIPT.read_text()

    for marker in (
        "validate_health_response(health)",
        "validate_dashboard_identity(dashboard, instance)",
        "validate_sidebar_coverage(paths)",
        "response.read(MAX_RESPONSE_BYTES + 1)",
        "if len(body) > MAX_RESPONSE_BYTES:",
        "auth.revoke(token)",
        "SIDEBAR_FAILURES=",
    ):
        assert marker in source
