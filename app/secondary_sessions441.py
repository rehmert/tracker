"""Release 441: secondary-session review and scoped revocation.

The API accepts only the raw session cookie, not a user ID or session ID.
User identity is resolved from the existing signed-in secondary session,
and the current session is revalidated under BEGIN IMMEDIATE before updates.
Normal administrator sessions and secondary sessions of other users are not
modified.
"""

import hashlib
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone

from . import session_auth385 as auth
from .user_accounts427 import staging_environment


def _identity441(db, token):
    """Resolve a valid secondary user and hashed current token."""
    if not isinstance(token, str) or not 40 <= len(token) <= 160:
        raise PermissionError("Secondary session required")
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    row = db.execute("""
        SELECT u.id, s.expires_at
        FROM tracker_secondary_sessions430 s
        JOIN users u ON u.id=s.user_id
        WHERE s.token_hash=? AND s.expires_at>?
          AND u.id>1 AND u.enabled=0
    """, (digest, int(time.time()))).fetchone()
    if row is None:
        raise PermissionError("Secondary session expired or revoked")
    return row[0], digest, row[1]


def _checked_session441(token):
    """Fail closed before opening a privileged session operation."""
    from .secondary_preview430 import _session_user, preview_enabled

    if not preview_enabled():
        raise PermissionError("Secondary gateway disabled")
    staging_environment()
    uid = _session_user(token)
    if uid is None:
        raise PermissionError("Secondary session required")
    return uid


def session_overview441(token):
    """Return only a count and current session expiry, not token hashes."""
    uid = _checked_session441(token)
    with closing(auth.connect()) as db:
        other_uid, digest, expiry = _identity441(db, token)
        if uid != other_uid:
            raise PermissionError("Secondary session identity changed")
        count = db.execute("""
            SELECT COUNT(*) FROM tracker_secondary_sessions430
            WHERE user_id=? AND expires_at>?
        """, (uid, int(time.time()))).fetchone()[0]
    return {
        "active_sessions": int(count),
        "other_sessions": max(0, int(count) - 1),
        "current_expires_utc": datetime.fromtimestamp(
            expiry, timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC"),
    }


def revoke_other_sessions441(token):
    """Transactionally delete only other sessions for the signed-in user."""
    uid = _checked_session441(token)
    with closing(auth.connect()) as db:
        try:
            db.execute("BEGIN IMMEDIATE")
            other_uid, digest, expiry = _identity441(db, token)
            if other_uid != uid:
                raise PermissionError("Secondary session identity changed")
            count = db.execute("""
                DELETE FROM tracker_secondary_sessions430
                WHERE user_id=? AND token_hash<>?
            """, (uid, digest)).rowcount
            db.commit()
        except BaseException:
            db.rollback()
            raise

    return int(count)
