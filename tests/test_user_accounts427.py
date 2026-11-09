"""Release 427 secondary-account credential isolation."""

from contextlib import closing
import sqlite3

import pytest

from app import config, session_auth385 as auth
from app.user_bootstrap426 import initialize_staged_workspace426
from app.user_accounts427 import (
    stage_secondary_account427,
    inspect_staged_account427,
    staged_credential_matches427,
    list_staged_accounts427,
)
from app.user_storage388 import live_storage_for


@pytest.fixture
def staging(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        config, "instance_label", lambda: "DEV"
    )

    auth.bootstrap(
        "operator",
        "administrator-secure-password-427",
    )

    (tmp_path / auth.FLAG).write_text("enabled")

    initialize_staged_workspace426(2, tmp_path)
    initialize_staged_workspace426(3, tmp_path)

    return tmp_path


def test_secondary_account_is_disabled(staging):
    result = stage_secondary_account427(
        2,
        "member-two",
        "secondary-secure-password-427",
    )

    assert result["user_id"] == 2
    assert result["username"] == "member-two"
    assert result["credential_status"] == "disabled"
    assert result["workspace_status"] == "inactive"
    assert result["login_enabled"] is False
    assert result["live_data_access_enabled"] is False

    with closing(auth.connect()) as db:
        assert db.execute("""
            SELECT enabled FROM users WHERE id=2
        """).fetchone() == (0,)

        assert db.execute("""
            SELECT COUNT(*) FROM sessions WHERE user_id=2
        """).fetchone()[0] == 0


def test_independent_credential_hashing(staging):
    stage_secondary_account427(
        2, "member-two", "unique-secret-for-two"
    )
    stage_secondary_account427(
        3, "member-three", "unique-secret-for-three"
    )

    assert staged_credential_matches427(
        2, "member-two", "unique-secret-for-two"
    )
    assert not staged_credential_matches427(
        2, "member-two", "unique-secret-for-three"
    )
    assert staged_credential_matches427(
        3, "member-three", "unique-secret-for-three"
    )
    assert not staged_credential_matches427(
        3, "member-three", "unique-secret-for-two"
    )

    with closing(auth.connect()) as db:
        first = db.execute("""
            SELECT salt,password_hash FROM users WHERE id=2
        """).fetchone()

        second = db.execute("""
            SELECT salt,password_hash FROM users WHERE id=3
        """).fetchone()

    assert first[0] != second[0]
    assert first[1] != second[1]


def test_admin_login_and_sessions_unchanged(staging):
    stage_secondary_account427(
        2, "member-two", "secondary-secure-password-427"
    )

    assert auth.verify_admin(
        "operator", "administrator-secure-password-427"
    )

    assert not auth.verify_admin(
        "member-two", "secondary-secure-password-427"
    )

    token, _ = auth.create_session(False)

    assert auth.session_user(token) == 1

    with closing(auth.connect()) as db:
        assert db.execute("""
            SELECT COUNT(*) FROM sessions WHERE user_id=2
        """).fetchone()[0] == 0


def test_disabled_account_cannot_access_live_workspace(staging):
    stage_secondary_account427(
        2, "member-two", "secondary-secure-password-427"
    )

    with pytest.raises(PermissionError):
        live_storage_for(2)


def test_duplicate_names_and_ids_are_rejected(staging):
    stage_secondary_account427(
        2, "member-two", "secondary-secure-password-427"
    )

    with pytest.raises(FileExistsError):
        stage_secondary_account427(
            2, "another-name", "another-long-password"
        )

    with pytest.raises(FileExistsError):
        stage_secondary_account427(
            3, "MEMBER-TWO", "another-long-password"
        )

    with pytest.raises(FileExistsError):
        stage_secondary_account427(
            3, "OPERATOR", "another-long-password"
        )


def test_missing_workspace_is_rejected(staging):
    with pytest.raises(RuntimeError):
        stage_secondary_account427(
            4, "member-four", "another-long-password"
        )

    with closing(auth.connect()) as db:
        assert db.execute("""
            SELECT COUNT(*) FROM users WHERE id=4
        """).fetchone()[0] == 0


@pytest.mark.parametrize(
    "value",
    ["", " " * 20, "x" * 1025],
)
def test_weak_or_invalid_password_is_rejected(staging, value):
    with pytest.raises(ValueError):
        stage_secondary_account427(
            2, "member-two", value
        )


@pytest.mark.parametrize(
    "value",
    ["a", "../bad", "white space", "x" * 81],
)
def test_invalid_username_is_rejected(staging, value):
    with pytest.raises(ValueError):
        stage_secondary_account427(
            2, value, "long-secure-password-427"
        )


def test_user_one_cannot_be_reprovisioned(staging):
    with pytest.raises(PermissionError):
        stage_secondary_account427(
            1, "operator2", "long-secure-password-427"
        )


def test_account_inventory_has_no_secrets(staging):
    stage_secondary_account427(
        2, "member-two", "secondary-secure-password-427"
    )

    accounts = list_staged_accounts427()

    assert len(accounts) == 1
    assert accounts[0]["user_id"] == 2
    assert "password_hash" not in accounts[0]
    assert "salt" not in accounts[0]

    assert inspect_staged_account427(
        2
    ) == accounts[0]


def test_unexpected_activation_is_fail_closed(staging):
    stage_secondary_account427(
        2, "member-two", "secondary-secure-password-427"
    )

    with closing(auth.connect()) as db:
        with db:
            db.execute("""
                UPDATE users SET enabled=1 WHERE id=2
            """)

    with pytest.raises(RuntimeError):
        inspect_staged_account427(2)

    with pytest.raises(RuntimeError):
        list_staged_accounts427()


def test_production_cannot_stage_accounts(staging, monkeypatch):
    monkeypatch.setattr(
        config, "instance_label", lambda: "PROD"
    )

    stage_secondary_account427(
        2, "member-two", "secondary-secure-password-427"
    )
    accounts = list_staged_accounts427()
    assert any(a["user_id"] == 2 for a in accounts)


def test_legacy_admin_database_is_untouched(staging):
    legacy = staging / "tracker.db"

    with sqlite3.connect(legacy) as db:
        db.execute("""
            CREATE TABLE private_data (value TEXT)
        """)
        db.execute("""
            INSERT INTO private_data VALUES ('admin-private')
        """)

    original = legacy.read_bytes()

    stage_secondary_account427(
        2, "member-two", "secondary-secure-password-427"
    )

    assert legacy.read_bytes() == original



def test_secondary_short_password_accepted(staging):
    result = stage_secondary_account427(
        2, "member-two", "abc"
    )

    assert result["user_id"] == 2
    assert staged_credential_matches427(
        2, "member-two", "abc"
    )
    assert not staged_credential_matches427(
        2, "member-two", "wrong"
    )
