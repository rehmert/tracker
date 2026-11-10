"""Release 550: strictly validate the configured service port."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke550", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configure(smoke, monkeypatch, exec_start):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout=exec_start)

    monkeypatch.setattr(
        smoke.subprocess, "run", fake_run
    )

    return calls


@pytest.mark.parametrize(
    "port",
    [1, 80, 8000, 8080, 65535],
)
def test_valid_service_ports550(smoke, monkeypatch, port):
    calls = configure(
        smoke,
        monkeypatch,
        f"/opt/tracker/.venv/bin/uvicorn "
        f"app.main:app --port {port} ;",
    )

    assert smoke.port_from_service() == port
    assert len(calls) == 1

    assert calls[0][0] == [
        "systemctl",
        "show",
        "tracker",
        "-p",
        "ExecStart",
        "--value",
    ]


@pytest.mark.parametrize(
    "port",
    [1, 8000, 65535],
)
def test_equals_form_port550(smoke, monkeypatch, port):
    configure(
        smoke,
        monkeypatch,
        f"/opt/tracker/uvicorn --port={port}",
    )

    assert smoke.port_from_service() == port


@pytest.mark.parametrize(
    "exec_start",
    [
        "",
        "/opt/tracker/uvicorn app.main:app",
        "/opt/tracker/uvicorn --port",
        "/opt/tracker/uvicorn --port nope",
        "/opt/tracker/uvicorn --port 8000garbage",
        "/opt/tracker/uvicorn --port -1",
        "/opt/tracker/uvicorn --port=",
    ],
)
def test_missing_or_malformed_port550(
    smoke, monkeypatch, exec_start
):
    configure(smoke, monkeypatch, exec_start)

    with pytest.raises(
        ValueError,
        match="no valid --port",
    ):
        smoke.port_from_service()


@pytest.mark.parametrize(
    "port",
    [0, 65536, 99999],
)
def test_out_of_range_port550(
    smoke, monkeypatch, port
):
    configure(
        smoke,
        monkeypatch,
        f"/opt/tracker/uvicorn --port {port}",
    )

    with pytest.raises(
        ValueError,
        match="port out of range",
    ):
        smoke.port_from_service()


def test_no_implicit_port_fallback550():
    source = SCRIPT.read_text()

    function = source.split(
        "def port_from_service():", 1
    )[1].split(
        "def service_working_directory():", 1
    )[0]

    assert "if match is None:" in function
    assert "if not 1 <= port <= 65535:" in function
    assert "return port" in function
    assert "if match else 8000" not in function


def test_prior_security_guards_preserved550():
    source = SCRIPT.read_text()

    for marker in (
        "validate_health_response(health)",
        "validate_dashboard_identity(dashboard, instance)",
        "validate_sidebar_coverage(paths)",
        "response.read(MAX_RESPONSE_BYTES + 1)",
        "if len(body) > MAX_RESPONSE_BYTES:",
        "Authenticated sidebar rejected: ",
        "auth.revoke(token)",
        "SIDEBAR_FAILURES=",
    ):
        assert marker in source
