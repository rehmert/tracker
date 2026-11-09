"""Release 523: PROD migration is explicit, reversible, and secret-safe.

Tests use temporary local paths, never systemctl, /etc/tracker.env,
real accounts or installed Tracker data.
"""
import importlib.util
import os
import sqlite3
import stat
from pathlib import Path

import pytest


def _module():
    spec = importlib.util.spec_from_file_location(
        "prod_parity523", "scripts/tracker-prod-parity523.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cutover(tmp_path, monkeypatch):
    script = _module()
    script.ROOT = tmp_path / "tracker"
    script.ROOT.mkdir()
    script.ENV = tmp_path / "tracker.env"
    script.OVERRIDE = tmp_path / "tracker-parity523.env"
    script.DROPIN_DIR = tmp_path / "systemd" / "tracker.service.d"
    script.DROPIN = script.DROPIN_DIR / "90-tracker-parity523.conf"

    data = script.ROOT / "data"
    data.mkdir()
    db = data / "tracker.db"
    with sqlite3.connect(db):
        pass
    db.chmod(0o600)

    script.ENV.write_text(
        "TRACKER_INSTANCE=PROD\n"
        "TRACKER_USER=operator\n"
        "TRACKER_PASS=secret-production-only\n"
        f"TRACKER_DATA_DIR={data}\n"
    )
    return script, data, monkeypatch


def test_523_config_parser_is_prod_only_and_never_prints_secrets(cutover):
    script, data, _ = cutover
    values, resolved, db = script.settings()
    assert values["TRACKER_INSTANCE"] == "PROD"
    assert values["TRACKER_PASS"] == "secret-production-only"
    assert resolved == data
    assert db == data / "tracker.db"
    script.ENV.write_text(script.ENV.read_text().replace(
        "TRACKER_INSTANCE=PROD", "TRACKER_INSTANCE=DEV"
    ))
    with pytest.raises(RuntimeError, match="outside PROD"):
        script.settings()


def test_523_real_auth_bootstrap_remains_in_private_prod_data(cutover):
    script, data, monkeypatch = cutover
    from app import config
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "instance_label", lambda: "PROD")

    values, _, db = script.settings()
    # prepare_auth intentionally sets process-local runtime variables.
    # Register their originals with monkeypatch so no test worker leaks
    # PROD identity into unrelated DEV/default backend tests.
    monkeypatch.setenv("TRACKER_INSTANCE", "PROD")
    monkeypatch.setenv("TRACKER_PROD_PARITY523", "1")
    monkeypatch.setenv("TRACKER_DATA_DIR", str(data))
    marker, uid, gid = script.prepare_auth(values, data, db)
    from app import session_auth385 as auth

    assert marker == data / auth.PROD_FLAG523
    assert not marker.exists()
    assert (data / auth.DATABASE).is_file()
    assert stat.S_IMODE((data / auth.DATABASE).stat().st_mode) == 0o600
    assert auth.verify_admin("operator", "secret-production-only")
    assert (data / "tracker.db").is_file()
    assert uid == db.stat().st_uid and gid == db.stat().st_gid


def test_523_mocked_cutover_enables_expected_flags_and_marker(cutover, monkeypatch):
    script, data, _ = cutover
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    environment = {"TRACKER_INSTANCE": "PROD"}

    def fake_run(*args):
        if args[:2] == ("systemctl", "is-active"):
            return "active"
        if "branch" in args:
            return "main"
        if "status" in args:
            return ""
        if args[:2] == ("systemctl", "restart"):
            if script.OVERRIDE.exists():
                environment.update({name: "1" for name in script.FLAGS})
            else:
                for key in script.FLAGS:
                    environment.pop(key, None)
        return ""

    monkeypatch.setattr(script, "run", fake_run)
    monkeypatch.setattr(script, "process_env", lambda: environment)
    monkeypatch.setattr(script, "verify_login", lambda: None)
    monkeypatch.setattr(script, "backup", lambda: None)
    monkeypatch.setattr(script, "prepare_auth", lambda values, root, db: (
        root / script.MARKER, os.getuid(), os.getgid()
    ))

    script.activate()
    assert script.OVERRIDE.is_file()
    assert script.DROPIN.is_file()
    assert (data / script.MARKER).is_file()
    assert all(environment[key] == "1" for key in script.FLAGS)


def test_523_mocked_failed_smoke_rolls_back_basic_auth(cutover, monkeypatch):
    script, data, _ = cutover
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    environment = {"TRACKER_INSTANCE": "PROD"}

    def fake_run(*args):
        if args[:2] == ("systemctl", "is-active"):
            return "active"
        if "branch" in args:
            return "main"
        if "status" in args:
            return ""
        if args[:2] == ("systemctl", "restart"):
            if script.OVERRIDE.exists():
                environment.update({name: "1" for name in script.FLAGS})
            else:
                for key in script.FLAGS:
                    environment.pop(key, None)
        return ""

    monkeypatch.setattr(script, "run", fake_run)
    monkeypatch.setattr(script, "process_env", lambda: environment)
    monkeypatch.setattr(script, "backup", lambda: None)
    monkeypatch.setattr(script, "verify_login", lambda: (
        (_ for _ in ()).throw(RuntimeError("Mocked health failure"))
    ))
    monkeypatch.setattr(script, "prepare_auth", lambda values, root, db: (
        root / script.MARKER, os.getuid(), os.getgid()
    ))

    with pytest.raises(RuntimeError, match="Mocked health failure"):
        script.activate()

    assert not script.OVERRIDE.exists()
    assert not script.DROPIN.exists()
    assert not (data / script.MARKER).exists()
    assert environment.get("TRACKER_PROD_PARITY523") is None


def test_523_cutover_source_has_no_credential_output_or_live_shortcuts():
    path = Path("scripts/tracker-prod-parity523.py")
    source = path.read_text()
    assert "TRACKER_PASS" in source
    assert "secret-production-only" not in source
    assert "git reset --hard" not in source
    assert "X-Forwarded-Host" not in source
    assert "PROD_LOGIN_PARITY523=ENABLED" in source
    assert "ROLLBACK:" in source
