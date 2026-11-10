"""Release 536: read-only configuration security audit."""

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/tracker-security-audit536.py"
)


@pytest.fixture
def audit():
    spec = importlib.util.spec_from_file_location(
        "tracker_security_audit536", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_env(tmp_path, content, mode=0o600):
    path = tmp_path / "tracker.env"
    path.write_text(content)
    path.chmod(mode)
    return path


def test_basic_auth_and_strict_settings_are_accepted536(
    audit, tmp_path,
):
    data = tmp_path / "data"
    env = make_env(
        tmp_path,
        f"TRACKER_INSTANCE=DEV\n"
        f"TRACKER_DATA_DIR={data}\n"
        "TRACKER_USER=operator\n"
        "TRACKER_PASS=private-value\n"
        "TRACKER_CSRF_ENFORCE=1\n"
        "TRACKER_ORIGIN_GUARD=1\n",
    )
    settings = audit.parse_env_file(env)
    findings = audit.inspect(settings, env, "DEV")

    assert not [
        code for code, severity, _ in findings
        if severity == "HIGH"
    ]
    assert any(
        code == "BASIC_AUTH"
        for code, _, _ in findings
    )


def test_session_marker_and_store_are_detected536(
    audit, tmp_path,
):
    data = tmp_path / "data"
    data.mkdir()
    (data / ".tracker-session-auth-dev").touch()
    (data / "tracker-auth.sqlite3").touch()

    env = make_env(
        tmp_path,
        f"TRACKER_INSTANCE=PROD\nTRACKER_DATA_DIR={data}\n",
    )
    findings = audit.inspect(
        audit.parse_env_file(env), env, "PROD"
    )

    assert any(
        code == "SESSION_AUTH" and level == "OK"
        for code, level, _ in findings
    )
    assert not any(
        code == "NO_AUTH_CONFIG"
        for code, _, _ in findings
    )


def test_missing_store_is_high_risk536(audit, tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / ".tracker-session-auth-dev").touch()

    env = make_env(
        tmp_path,
        f"TRACKER_INSTANCE=DEV\nTRACKER_DATA_DIR={data}\n",
    )
    findings = audit.inspect(
        audit.parse_env_file(env), env, "DEV"
    )

    assert any(
        code == "SESSION_STORE_UNAVAILABLE"
        and level == "HIGH"
        for code, level, _ in findings
    )


def test_partial_basic_and_disabled_origin_are_flagged536(
    audit, tmp_path,
):
    env = make_env(
        tmp_path,
        "TRACKER_INSTANCE=DEV\n"
        "TRACKER_USER=operator\n"
        "TRACKER_ORIGIN_GUARD=0\n",
    )
    findings = audit.inspect(
        audit.parse_env_file(env), env, "DEV"
    )
    codes = {
        code for code, level, _ in findings
        if level == "HIGH"
    }

    assert "PARTIAL_BASIC_AUTH" in codes
    assert "ORIGIN_GUARD_DISABLED" in codes


def test_report_only_is_warning536(audit, tmp_path):
    env = make_env(
        tmp_path,
        "TRACKER_INSTANCE=DEV\n"
        "TRACKER_USER=operator\n"
        "TRACKER_PASS=password\n",
    )
    findings = audit.inspect(
        audit.parse_env_file(env), env, "DEV"
    )

    assert any(
        code == "CSRF_REPORT_ONLY"
        and level == "WARN"
        for code, level, _ in findings
    )


def test_mismatched_instance_is_high_risk536(audit, tmp_path):
    env = make_env(
        tmp_path,
        "TRACKER_INSTANCE=DEV\n"
        "TRACKER_USER=operator\n"
        "TRACKER_PASS=password\n",
    )
    findings = audit.inspect(
        audit.parse_env_file(env), env, "PROD"
    )

    assert any(
        code == "INSTANCE_MISMATCH"
        and level == "HIGH"
        for code, level, _ in findings
    )


def test_duplicate_settings_are_rejected536(audit, tmp_path):
    env = make_env(
        tmp_path,
        "TRACKER_USER=one\nTRACKER_USER=two\n",
    )

    with pytest.raises(audit.AuditError):
        audit.parse_env_file(env)


def test_symlink_envfile_is_refused536(audit, tmp_path):
    target = make_env(
        tmp_path,
        "TRACKER_INSTANCE=DEV\n",
    )
    link = tmp_path / "linked.env"
    link.symlink_to(target)

    with pytest.raises(audit.AuditError):
        audit.parse_env_file(link)


def test_sensitive_values_never_printed536(
    audit, tmp_path, capsys,
):
    secret = "SHOULD_NOT_APPEAR_IN_OUTPUT_536"
    env = make_env(
        tmp_path,
        "TRACKER_INSTANCE=DEV\n"
        "TRACKER_USER=operator\n"
        f"TRACKER_PASS={secret}\n",
    )

    assert audit.main([
        "--envfile", str(env),
        "--instance", "DEV",
    ]) == 0

    output = capsys.readouterr().out
    assert secret not in output
    assert "SECURITY_AUDIT=PASS" in output


def test_fail_on_risk_returns_two536(
    audit, tmp_path, capsys,
):
    env = make_env(
        tmp_path,
        "TRACKER_INSTANCE=DEV\n"
        "TRACKER_ORIGIN_GUARD=0\n",
    )

    assert audit.main([
        "--envfile", str(env),
        "--instance", "DEV",
        "--fail-on-risk",
    ]) == 2

    assert (
        "SECURITY_AUDIT=RISK"
        in capsys.readouterr().out
    )


def test_invalid_env_syntax_has_no_secret_echo536(
    audit, tmp_path, capsys,
):
    secret = "SUPER_SECRET_536"
    env = make_env(
        tmp_path,
        f'TRACKER_PASS="{secret}\n',
    )

    assert audit.main([
        "--envfile", str(env),
    ]) == 1

    output = capsys.readouterr().out
    assert secret not in output
    assert "SECURITY_AUDIT=ERROR" in output


def test_envfile_permissions_warn536(audit, tmp_path):
    env = make_env(
        tmp_path,
        "TRACKER_INSTANCE=DEV\n",
        mode=0o644,
    )
    findings = audit.inspect(
        audit.parse_env_file(env), env, "DEV"
    )

    assert any(
        code == "ENVFILE_PERMISSIONS"
        and level == "WARN"
        for code, level, _ in findings
    )
