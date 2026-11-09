"""Release 466: multi-user cutover rehearsal tests."""

import json

import pytest

from app.secondary_cutover466 import (
    BLOCKERS466,
    CHECKS466,
    validate_report466,
    render_cutover466,
    assess_cutover466,
)


def staged466(uid, name):
    return {
        "user_id": uid,
        "username": name,
        "credential_status": "disabled",
        "workspace_status": "inactive",
        "login_enabled": False,
        "live_data_access_enabled": False,
    }


def sample_report466():
    return {
        "mode": "offline-cutover-rehearsal466",
        "checks": {
            key: True for key in CHECKS466
        },
        "staged_account_count": 2,
        "staged_user_ids": [2, 3],
        "cutover_blockers": list(BLOCKERS466),
        "normal_login_ready": False,
        "production_ready": False,
    }


def test_cutover466_fail_closed_report():
    report = sample_report466()
    assert validate_report466(report) == report

    for bad in (
        dict(report, production_ready=True),
        dict(report, normal_login_ready=True),
        dict(report, staged_user_ids=[2, 2]),
        dict(report, staged_user_ids=[1, 3]),
        dict(report, cutover_blockers=[]),
        dict(report, checks={
            **report["checks"],
            "private_storage_separated": False,
        }),
        dict(report, database_path="/tmp/private"),
    ):
        with pytest.raises(ValueError):
            validate_report466(bad)


def test_cutover466_escaped_and_private():
    html = render_cutover466(
        staged466(2, '<script>bad</script>')
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Remaining Architectural Work" in html
    assert "normal application login not enabled" in html
    assert "member-3" not in html

    for bad in (
        dict(staged466(2, "member-2"),
             login_enabled=True),
        dict(staged466(2, "member-2"),
             workspace_status="active"),
    ):
        with pytest.raises(ValueError):
            render_cutover466(bad)


def test_cutover466_source_is_read_only():
    from pathlib import Path

    text = Path(
        "app/secondary_cutover466.py"
    ).read_text()

    forbidden = (
        "UPDATE users",
        "INSERT INTO users",
        "DELETE FROM users",
        "CREATE TABLE",
        "enabled=1",
        "session_cookie",
        "create_session(",
        "set_cookie(",
        "write_text(",
        "write_bytes(",
        "subprocess.run(",
    )

    for marker in forbidden:
        assert marker not in text, marker

    assert "live_storage_for(2)" in text
    assert "normal_login_ready" in text


def test_cutover466_dev_audit_isolation(
    monkeypatch, tmp_path
):
    from app import config, session_auth385 as auth
    from app.user_bootstrap426 import (
        initialize_staged_workspace426,
    )
    from app.user_accounts427 import stage_secondary_account427

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        config, "instance_label", lambda: "DEV"
    )

    auth.bootstrap(
        "operator",
        "administrator-secure-password-466",
    )
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}",
            f"secure-member-{uid}-password-466",
        )

    report = assess_cutover466()

    assert report["staged_account_count"] == 2
    assert report["staged_user_ids"] == [2, 3]
    assert report["normal_login_ready"] is False
    assert report["production_ready"] is False
    assert all(report["checks"].values())

    # No username, password, session or filesystem path
    # is included in the system audit.
    serialized = json.dumps(report)
    for forbidden in (
        "secure-member",
        "password_hash",
        "session_token",
        str(tmp_path),
    ):
        assert forbidden not in serialized

    monkeypatch.setattr(
        config, "instance_label", lambda: "PROD"
    )
    prod_report = assess_cutover466()
    assert prod_report == report
