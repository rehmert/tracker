"""Release 427: offline staging of secondary Tracker credentials.

Secondary accounts are ALWAYS stored disabled. No HTTP login
endpoint, live workspace router, or application session uses
these accounts.

The existing DEV administrator authentication database is reused.
Production authentication remains unchanged.
"""

import hmac
import re
import secrets
import stat
from contextlib import closing
from pathlib import Path

from .instance_parity523 import interactive_parity523
from . import config
from . import session_auth385 as auth
from .user_bootstrap426 import (
    verify_staged_workspace426,
    _reject_symlink_components,
)
from .user_storage388 import valid_user_id


USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_.@-]{2,80}\Z")


def secondary_id(user_id):
    uid = valid_user_id(user_id)
    if uid <= 1:
        raise PermissionError(
            "Administrator identity cannot be staged"
        )
    return uid


def staging_environment(data_root=None):
    """Require a real DEV authentication store and trusted data root."""
    if not interactive_parity523() or not auth.enabled():
        raise PermissionError(
            "Secondary account staging requires DEV session mode"
        )

    root = _reject_symlink_components(config.DATA_DIR)

    if data_root is not None:
        requested = _reject_symlink_components(data_root)
        if requested != root:
            raise ValueError(
                "Account storage must match configured data root"
            )

    path = _reject_symlink_components(auth.database_path())

    if not path.is_file():
        raise RuntimeError("Authentication database unavailable")

    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise RuntimeError(
            "Authentication database permissions are unsafe"
        )

    return root


def validate_username(username):
    if not isinstance(username, str):
        raise ValueError("Invalid username")

    normalized = username.strip()

    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Username must contain 2–80 allowed characters"
        )

    return normalized


def validate_password(password):
    # No minimum length or character-composition policy.
    # Retain a transport/resource limit and reject blanks.
    if (
        not isinstance(password, str)
        or not password.strip()
        or len(password) > 1024
    ):
        raise ValueError(
            "Password must be nonempty and at most 1024 characters"
        )

    return password


def _administrator_present(db):
    row = db.execute("""
        SELECT id FROM users
        WHERE id=1 AND enabled=1
    """).fetchone()

    if row != (1,):
        raise RuntimeError(
            "Enabled legacy administrator account required"
        )


def _secondary_accounts_locked(db):
    """Fail if any secondary account has been activated or given sessions."""
    active = db.execute("""
        SELECT id FROM users
        WHERE id>1 AND enabled<>0
        LIMIT 1
    """).fetchone()

    sessions = db.execute("""
        SELECT user_id FROM sessions
        WHERE user_id>1
        LIMIT 1
    """).fetchone()

    if active or sessions:
        raise RuntimeError(
            "Unexpected secondary account activation or session"
        )


def stage_secondary_account427(
    user_id, username, password, data_root=None
):
    """Store an independently hashed credential, disabled by design."""
    uid = secondary_id(user_id)
    name = validate_username(username)
    secret = validate_password(password)
    root = staging_environment(data_root)

    # The private user database must be schema-ready and inactive.
    verify_staged_workspace426(uid, root)

    salt = secrets.token_bytes(16)
    digest = auth.password_digest(secret, salt)

    with closing(auth.connect()) as db:
        db.execute("BEGIN IMMEDIATE")

        _administrator_present(db)
        _secondary_accounts_locked(db)

        duplicate = db.execute("""
            SELECT id FROM users
            WHERE id=? OR lower(username)=lower(?)
            LIMIT 1
        """, (uid, name)).fetchone()

        if duplicate:
            raise FileExistsError(
                "Account ID or username already exists"
            )

        db.execute("""
            INSERT INTO users
                (id, username, salt, password_hash, enabled)
            VALUES (?, ?, ?, ?, 0)
        """, (uid, name, salt, digest))

        db.commit()

    return inspect_staged_account427(uid, root)


def inspect_staged_account427(user_id, data_root=None):
    """Read-only check; never returns passwords or password hashes."""
    uid = secondary_id(user_id)
    root = staging_environment(data_root)

    workspace = verify_staged_workspace426(uid, root)

    with closing(auth.connect()) as db:
        _administrator_present(db)
        _secondary_accounts_locked(db)

        row = db.execute("""
            SELECT username, enabled, length(salt),
                   length(password_hash)
            FROM users WHERE id=?
        """, (uid,)).fetchone()

        if (
            row is None
            or row[1] != 0
            or row[2] != 16
            or row[3] != 32
        ):
            raise RuntimeError(
                "Staged credential unavailable or invalid"
            )

    return {
        "user_id": uid,
        "username": row[0],
        "credential_status": "disabled",
        "workspace_status": workspace["status"],
        "login_enabled": False,
        "live_data_access_enabled": False,
    }


def staged_credential_matches427(user_id, username, password):
    """Offline credential check ONLY; does not authenticate HTTP requests."""
    uid = secondary_id(user_id)
    name = validate_username(username)

    if not isinstance(password, str) or len(password) > 1024:
        return False

    staging_environment()

    with closing(auth.connect()) as db:
        _secondary_accounts_locked(db)

        row = db.execute("""
            SELECT salt, password_hash
            FROM users
            WHERE id=? AND username=? AND enabled=0
        """, (uid, name)).fetchone()

    if row is None:
        return False

    try:
        digest = auth.password_digest(password, row[0])
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(digest, row[1])


def list_staged_accounts427():
    """Read-only inventory of disabled secondary accounts."""
    root = staging_environment()

    with closing(auth.connect()) as db:
        _administrator_present(db)
        _secondary_accounts_locked(db)

        rows = db.execute("""
            SELECT id FROM users
            WHERE id>1 AND enabled=0
            ORDER BY id
        """).fetchall()

    return [
        inspect_staged_account427(uid, root)
        for (uid,) in rows
    ]
