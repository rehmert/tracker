"""DEV-only editing of existing secondary user credentials."""

import secrets
from contextlib import closing

from . import config, session_auth385 as auth
from .user_accounts427 import (
    secondary_id,
    staging_environment,
    validate_username,
    validate_password,
    inspect_staged_account427,
    _administrator_present,
    _secondary_accounts_locked,
)


def edit_secondary_account480(user_id, username, password=None):
    if config.instance_label() != "DEV" or not auth.enabled():
        raise PermissionError("DEV mode required")

    uid = secondary_id(user_id)
    name = validate_username(username)
    staging_environment()

    # Never edit an account whose private workspace fails
    # validation. Nothing in that workspace is modified here.
    inspect_staged_account427(uid)

    if password is not None:
        secret = validate_password(password)
        salt = secrets.token_bytes(16)
        digest = auth.password_digest(secret, salt)
    else:
        salt = digest = None

    with closing(auth.connect()) as db:
        try:
            db.execute("BEGIN IMMEDIATE")
            _administrator_present(db)
            _secondary_accounts_locked(db)

            row = db.execute("""
                SELECT username
                FROM users
                WHERE id=? AND id>1 AND enabled=0
            """, (uid,)).fetchone()

            if row is None:
                raise LookupError("Secondary account missing")

            old_name = row[0]

            collision = db.execute("""
                SELECT id FROM users
                WHERE lower(username)=lower(?)
                  AND id<>?
                LIMIT 1
            """, (name, uid)).fetchone()

            if collision:
                raise FileExistsError("Username already exists")

            if old_name == name and password is None:
                raise ValueError("No changes requested")

            if password is None:
                updated = db.execute("""
                    UPDATE users SET username=?
                    WHERE id=? AND enabled=0
                """, (name, uid))
            else:
                updated = db.execute("""
                    UPDATE users
                    SET username=?, salt=?, password_hash=?
                    WHERE id=? AND enabled=0
                """, (name, salt, digest, uid))

            if updated.rowcount != 1:
                raise RuntimeError("Account update failed")

            # A newly created secondary user may never have
            # logged in. In that case these session/failure
            # tables might not exist yet.
            available = {
                row[0] for row in db.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table'
                """).fetchall()
            }

            if "tracker_secondary_sessions430" in available:
                db.execute("""
                    DELETE FROM tracker_secondary_sessions430
                    WHERE user_id=?
                """, (uid,))

            if "tracker_secondary_failures430" in available:
                db.execute("""
                    DELETE FROM tracker_secondary_failures430
                    WHERE username IN (lower(?), lower(?))
                """, (old_name, name))

            db.commit()

        except BaseException:
            db.rollback()
            raise

    return inspect_staged_account427(uid)
