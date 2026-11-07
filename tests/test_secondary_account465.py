"""Release 465: staged-account readiness and audit tests."""

import json
import pytest

from app.secondary_account_readiness465 import (
    normalize_account465,
    render_account465,
    audit_accounts465,
)


def record(uid, username):
    return {
        "user_id": uid,
        "username": username,
        "credential_status": "disabled",
        "workspace_status": "inactive",
        "login_enabled": False,
        "live_data_access_enabled": False,
    }


def test_account465_strict_staged_contract():
    account = normalize_account465(
        record(2, "member-2")
    )

    assert account["user_id"] == 2
    assert account["normal_login_enabled"] is False
    assert account["pilot_login_only"] is True

    invalid = (
        dict(
            record(2, "member-2"),
            login_enabled=True,
        ),
        dict(
            record(2, "member-2"),
            live_data_access_enabled=True,
        ),
        dict(
            record(2, "member-2"),
            workspace_status="active",
        ),
        dict(
            record(2, "member-2"),
            credential_status="enabled",
        ),
        dict(
            record(2, "member-2"),
            token="not-allowed",
        ),
        record(1, "administrator"),
    )

    for item in invalid:
        with pytest.raises(ValueError):
            normalize_account465(item)


def test_account465_escaped_render_and_audit():
    html = render_account465(
        record(2, '<script>alert(1)</script>')
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Normal Tracker Login" in html
    assert "Production Access" in html

    result = audit_accounts465([
        record(2, "member-2"),
        record(3, "member-3"),
    ])

    assert result["staged_account_count"] == 2
    assert result["all_accounts_inactive"] is True
    assert (
        result["normal_multi_user_login_enabled"]
        is False
    )

    with pytest.raises(ValueError):
        audit_accounts465([
            record(2, "member-2"),
            record(3, "MEMBER-2"),
        ])

    serialized = json.dumps(result)

    assert "password_hash" not in serialized
    assert "session_token" not in serialized


def test_account465_rejects_unexpected_fields():
    item = record(2, "member-2")

    for extra in ("password", "salt", "database_path"):
        with pytest.raises(ValueError):
            normalize_account465(
                dict(item, **{extra: "secret"})
            )


def test_account465_no_mutation_interfaces():
    from pathlib import Path

    source = Path(
        "app/secondary_account_readiness465.py"
    ).read_text()

    for forbidden in (
        "UPDATE users",
        "DELETE FROM users",
        "INSERT INTO users",
        "enabled=1",
        "chmod(",
        "write_text(",
        "write_bytes(",
        "os.remove(",
        "os.unlink(",
    ):
        assert forbidden not in source, forbidden
