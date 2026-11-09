"""Release 526: DEV and PROD smoke authentication parity."""

import base64
import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "tracker-runtime-smoke.py"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "tracker_release526_smoke", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("instance", ["DEV", "PROD"])
def test_session_auth_uses_short_lived_revocable_cookie(
    smoke, monkeypatch, tmp_path, instance
):
    (tmp_path / ".tracker-session-auth-dev").touch()

    events = []
    token = "x" * 64

    class FakeDatabase:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, query, params):
            events.append(("expiry", query, params))

    fake_auth = types.ModuleType("app.session_auth385")
    fake_auth.COOKIE = "tracker_session"
    fake_auth.enabled = lambda: True
    fake_auth.create_session = lambda remember: (token, 43200)
    fake_auth.connect = lambda: FakeDatabase()
    fake_auth.revoke = lambda value: events.append(("revoke", value))

    fake_app = types.ModuleType("app")
    fake_app.__path__ = []
    fake_app.session_auth385 = fake_auth

    monkeypatch.setitem(sys.modules, "app", fake_app)
    monkeypatch.setitem(
        sys.modules, "app.session_auth385", fake_auth
    )

    settings = {
        "TRACKER_INSTANCE": instance,
        "TRACKER_DATA_DIR": str(tmp_path),
        "TRACKER_USER": "legacy",
        "TRACKER_PASS": "legacy-password",
    }

    with smoke.release_auth_headers(instance, settings) as headers:
        assert headers["Cookie"] == "tracker_session=" + token
        assert "Authorization" not in headers
        assert os.environ["TRACKER_INSTANCE"] == instance
        assert os.environ["TRACKER_DATA_DIR"] == str(tmp_path)
        assert any(event[0] == "expiry" for event in events)

    assert ("revoke", token) in events


@pytest.mark.parametrize("instance", ["DEV", "PROD"])
def test_basic_auth_remains_available_without_session_mode(
    smoke, tmp_path, instance
):
    settings = {
        "TRACKER_INSTANCE": instance,
        "TRACKER_DATA_DIR": str(tmp_path),
        "TRACKER_USER": "legacy",
        "TRACKER_PASS": "secret",
    }

    with smoke.release_auth_headers(instance, settings) as headers:
        assert "Cookie" not in headers
        assert headers["Authorization"] == (
            "Basic "
            + base64.b64encode(b"legacy:secret").decode()
        )


@pytest.mark.parametrize("instance", ["DEV", "PROD"])
def test_disabled_session_auth_fails_closed(
    smoke, monkeypatch, tmp_path, instance
):
    (tmp_path / ".tracker-session-auth-dev").touch()

    fake_auth = types.ModuleType("app.session_auth385")
    fake_auth.enabled = lambda: False

    fake_app = types.ModuleType("app")
    fake_app.__path__ = []
    fake_app.session_auth385 = fake_auth

    monkeypatch.setitem(sys.modules, "app", fake_app)
    monkeypatch.setitem(
        sys.modules, "app.session_auth385", fake_auth
    )

    with pytest.raises(ValueError, match="unavailable"):
        with smoke.release_auth_headers(
            instance,
            {
                "TRACKER_INSTANCE": instance,
                "TRACKER_DATA_DIR": str(tmp_path),
            },
        ):
            pass
