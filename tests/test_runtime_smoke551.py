"""Release 551: reject duplicate and ambiguous service ports."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke551", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configure(smoke, monkeypatch, command):
    def fake_run(args, **kwargs):
        assert args == [
            "systemctl", "show", "tracker",
            "-p", "ExecStart", "--value"
        ]
        assert kwargs["check"] is True
        return SimpleNamespace(stdout=command)

    monkeypatch.setattr(smoke.subprocess, "run", fake_run)


@pytest.mark.parametrize("port", [1, 80, 8000, 8080, 65535])
@pytest.mark.parametrize("separator", [" ", "="])
def test_single_valid_port551(
    smoke, monkeypatch, port, separator
):
    configure(
        smoke, monkeypatch,
        f"/opt/tracker/uvicorn app.main:app "
        f"--port{separator}{port} ;"
    )
    assert smoke.port_from_service() == port


@pytest.mark.parametrize(
    "command",
    [
        "--port 8000 --port 8001",
        "--port=8000 --port=8000",
        "--port 8000 --port=8001",
        "--port=8000 --port 8000",
        "--port 8000 --port nonsense",
        "--port nonsense --port 8000",
        "--port 8000 --port",
        "--port --port 8000",
    ],
)
def test_duplicate_ports_rejected551(
    smoke, monkeypatch, command
):
    configure(smoke, monkeypatch, command)

    with pytest.raises(
        ValueError, match="exactly one valid --port"
    ):
        smoke.port_from_service()


@pytest.mark.parametrize(
    "command",
    [
        "",
        "/opt/tracker/uvicorn app.main:app",
        "--port",
        "--port=",
        "--port nonsense",
        "--port -1",
        "--port 8000garbage",
        "--port=8000bad",
    ],
)
def test_malformed_port_rejected551(
    smoke, monkeypatch, command
):
    configure(smoke, monkeypatch, command)

    with pytest.raises(
        ValueError, match="no valid --port"
    ):
        smoke.port_from_service()


@pytest.mark.parametrize("port", [0, 65536, 99999])
def test_out_of_range_port_rejected551(
    smoke, monkeypatch, port
):
    configure(smoke, monkeypatch, f"--port {port}")

    with pytest.raises(
        ValueError, match="port out of range"
    ):
        smoke.port_from_service()


def test_prior_protections_preserved551():
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

    assert "if match else 8000" not in source
