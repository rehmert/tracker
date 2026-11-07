"""Release 451: authenticated self-service password rotation for DEV-only
secondary accounts.

Only the account resolved from a currently valid private preview session may
rotate its own credentials. The administrator's credentials and sessions, all
other secondary users, and every private Tracker workspace remain untouched.

A successful change revokes *all* preview sessions for that account. No normal
Tracker multi-user login is enabled by this module.
"""
from __future__ import annotations

import hmac
import secrets
import sqlite3
import time
from contextlib import closing

from . import session_auth385 as auth
from .secondary_sessions441 import _checked_session441, _identity441
from .secondary_preview430 import WINDOW


MAX_ATTEMPTS = 8


def change_secondary_password451(token, current_password, new_password):
    """Rotate the signed-in user's password; revoke all their sessions.

    Returns False for an incorrect password, weak/reused replacement, or a
    temporarily rate-limited account. Raises PermissionError for a revoked or
    invalid secondary preview session, without mutating other accounts.
    """
    uid = _checked_session441(token)

    if (
        not isinstance(current_password, str)
        or not isinstance(new_password, str)
        or len(current_password) > 1024
        or not 12 <= len(new_password) <= 1024
        or not new_password.strip()
        or hmac.compare_digest(
            current_password.encode("utf-8"), new_password.encode("utf-8")
        )
    ):
        return False

    with closing(auth.connect()) as db:
        try:
            # Important: revalidate the precise session *inside* the write
            # transaction. A session revoked between HTTP checks must fail.
            db.execute("BEGIN IMMEDIATE")
            checked_uid, _, _ = _identity441(db, token)
            if checked_uid != uid:
                raise PermissionError("Secondary session identity changed")

            row = db.execute("""
                SELECT username, salt, password_hash
                FROM users WHERE id=? AND id>1 AND enabled=0
            """, (uid,)).fetchone()
            if row is None:
                raise PermissionError("Secondary account unavailable")

            username, old_salt, old_hash = row
            name_key = username.casefold()
            now = int(time.time())

            # Share the established 15-minute, per-username login-failure
            # counter. Prevent an authenticated but compromised session
            # from making unlimited guesses at the current password.
            db.execute("""
                DELETE FROM tracker_secondary_failures430
                WHERE occurred_at < ?
            """, (now - WINDOW,))
            recent_attempts = db.execute("""
                SELECT COUNT(*) FROM tracker_secondary_failures430
                WHERE username=? AND occurred_at>=?
            """, (name_key, now - WINDOW)).fetchone()[0]
            if recent_attempts >= MAX_ATTEMPTS:
                db.commit()
                return False

            attempted = auth.password_digest(current_password, old_salt)
            if not hmac.compare_digest(attempted, old_hash):
                db.execute("""
                    INSERT INTO tracker_secondary_failures430
                        (username, occurred_at) VALUES (?,?)
                """, (name_key, now))
                db.commit()
                return False

            replacement_salt = secrets.token_bytes(16)
            replacement_hash = auth.password_digest(
                new_password, replacement_salt
            )
            updated = db.execute("""
                UPDATE users
                SET salt=?, password_hash=?
                WHERE id=? AND enabled=0
            """, (replacement_salt, replacement_hash, uid))
            if updated.rowcount != 1:
                raise RuntimeError("Secondary credential rotation failed")

            db.execute("""
                DELETE FROM tracker_secondary_sessions430
                WHERE user_id=?
            """, (uid,))
            db.execute("""
                DELETE FROM tracker_secondary_failures430
                WHERE username=?
            """, (name_key,))
            db.commit()
            return True
        except BaseException:
            db.rollback()
            raise
