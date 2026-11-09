"""Separate administrator sessions for explicitly enabled DEV/PROD instances.

Multi-user data isolation is NOT enabled. The existing
Tracker database remains the administrator's data.
"""

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from contextlib import closing

from .instance_parity523 import interactive_parity523
from . import config

COOKIE = "tracker_session"
FLAG = ".tracker-session-auth-dev"
PROD_FLAG523 = ".tracker-session-auth-prod523"
DATABASE = "tracker-auth.sqlite3"

SESSION_SECONDS = 12 * 3600
REMEMBER_SECONDS = 30 * 86400


def enabled():
    if not interactive_parity523():
        return False
    marker = PROD_FLAG523 if config.instance_label() == "PROD" else FLAG
    return (config.DATA_DIR / marker).is_file()


def database_path():
    return config.DATA_DIR / DATABASE


def connect():
    path = database_path()

    if not path.is_file() or path.is_symlink():
        raise RuntimeError("Authentication store unavailable")

    db = sqlite3.connect(str(path), timeout=5)
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        return db
    except BaseException:
        db.close()
        raise


def password_digest(password, salt):
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**15,
        r=8,
        p=1,
        dklen=32,
        maxmem=64 * 1024 * 1024,
    )


def bootstrap(username, password):
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{2,80}", username):
        raise ValueError("Invalid administrator username")

    if not password:
        raise ValueError("Administrator password is empty")

    path = database_path()

    if path.exists() or path.is_symlink():
        raise FileExistsError("Authentication store already exists")

    fd = os.open(
        path,
        os.O_CREAT | os.O_EXCL | os.O_RDWR
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    os.close(fd)

    try:
        salt = secrets.token_bytes(16)
        hashed = password_digest(password, salt)

        with closing(sqlite3.connect(str(path))) as conn, conn as db:
            db.executescript("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    enabled INTEGER NOT NULL
                );

                CREATE TABLE sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );

                CREATE TABLE failures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    occurred_at INTEGER NOT NULL
                );

                CREATE INDEX sessions_expiry
                    ON sessions(expires_at);

                CREATE INDEX failures_lookup
                    ON failures(username,occurred_at);
            """)

            db.execute("""
                INSERT INTO users
                (id,username,salt,password_hash,enabled)
                VALUES (1,?,?,?,1)
            """, (username, salt, hashed))

        os.chmod(path, 0o600)

    except BaseException:
        path.unlink(missing_ok=True)
        raise


def verify_admin(username, password):
    now = int(time.time())

    try:
        with closing(connect()) as conn, conn as db:
            db.execute(
                "DELETE FROM failures WHERE occurred_at < ?",
                (now - 900,),
            )

            count = db.execute("""
                SELECT COUNT(*) FROM failures
                WHERE username=? AND occurred_at>=?
            """, (username, now - 900)).fetchone()[0]

            # Bound attacks against alternate usernames too.
            global_attempts = db.execute("""
                SELECT COUNT(*) FROM failures
                WHERE occurred_at>=?
            """, (now - 900,)).fetchone()[0]

            if count >= 8 or global_attempts >= 40:
                return False

            record = db.execute("""
                SELECT salt,password_hash FROM users
                WHERE id=1 AND username=? AND enabled=1
            """, (username,)).fetchone()

            valid = False
            if record:
                hashed = password_digest(password, record[0])
                valid = hmac.compare_digest(
                    hashed, record[1]
                )

            if not valid:
                db.execute("""
                    INSERT INTO failures(username,occurred_at)
                    VALUES (?,?)
                """, (username, now))
                return False

            db.execute(
                "DELETE FROM failures WHERE username=?",
                (username,),
            )
            return True

    except (OSError, sqlite3.Error, RuntimeError):
        return False


def create_session(remember):
    raw = secrets.token_urlsafe(48)
    hashed = hashlib.sha256(raw.encode()).hexdigest()

    now = int(time.time())
    lifetime = (
        REMEMBER_SECONDS if remember else SESSION_SECONDS
    )

    with closing(connect()) as conn, conn as db:
        db.execute(
            "DELETE FROM sessions WHERE expires_at<=?",
            (now,),
        )

        db.execute("""
            INSERT INTO sessions(token_hash,user_id,expires_at)
            VALUES (?,1,?)
        """, (hashed, now + lifetime))

    return raw, lifetime


def session_user(token):
    if not isinstance(token, str):
        return None

    if not 40 <= len(token) <= 160:
        return None

    hashed = hashlib.sha256(token.encode()).hexdigest()

    try:
        with closing(connect()) as conn, conn as db:
            result = db.execute("""
                SELECT u.id FROM sessions s
                JOIN users u ON u.id=s.user_id
                WHERE s.token_hash=?
                  AND s.expires_at>?
                  AND u.id=1
                  AND u.enabled=1
            """, (hashed, int(time.time()))).fetchone()

        return result[0] if result else None

    except (OSError, sqlite3.Error, RuntimeError):
        return None


def revoke(token):
    if not token:
        return

    hashed = hashlib.sha256(token.encode()).hexdigest()

    with closing(connect()) as conn, conn as db:
        db.execute(
            "DELETE FROM sessions WHERE token_hash=?",
            (hashed,),
        )


def safe_next(value):
    value = str(value or "/")

    if (
        len(value) > 300
        or not value.startswith("/")
        or value.startswith("//")
        or "\\" in value
        or any(ord(ch) < 32 for ch in value)
        or value.startswith("/login")
        or value.startswith("/logout")
    ):
        return "/"

    return value


def current_admin(token):
    """Return admin identity only for a valid current session."""
    if session_user(token) != 1:
        return None

    with closing(connect()) as conn, conn as db:
        row = db.execute("""
            SELECT username FROM users
            WHERE id=1 AND enabled=1
        """).fetchone()
    return row[0] if row else None


def session_overview(token):
    """Return count and expiry of this administrator's sessions."""
    if session_user(token) != 1:
        raise PermissionError("Valid session required")

    now = int(time.time())
    current = hashlib.sha256(token.encode()).hexdigest()

    with closing(connect()) as conn, conn as db:
        rows = db.execute("""
            SELECT token_hash, expires_at
            FROM sessions
            WHERE user_id=1 AND expires_at>?
            ORDER BY expires_at DESC
        """, (now,)).fetchall()

    return [
        {
            "current": hmac.compare_digest(row[0], current),
            "expires_at": row[1],
        }
        for row in rows
    ]


def revoke_other_sessions(token):
    if session_user(token) != 1:
        raise PermissionError("Valid session required")

    current = hashlib.sha256(token.encode()).hexdigest()

    with closing(connect()) as conn, conn as db:
        result = db.execute("""
            DELETE FROM sessions
            WHERE user_id=1 AND token_hash<>?
        """, (current,))

    return result.rowcount


def change_password(token, current_password, new_password):
    """Atomically change credentials and revoke all sessions."""
    if session_user(token) != 1:
        raise PermissionError("Valid session required")

    if (
        not isinstance(new_password, str)
        or not 12 <= len(new_password) <= 1024
        or not isinstance(current_password, str)
        or len(current_password) > 1024
        or hmac.compare_digest(
            current_password.encode(), new_password.encode()
        )
    ):
        return False

    with closing(connect()) as conn, conn as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""
            SELECT salt, password_hash FROM users
            WHERE id=1 AND enabled=1
        """).fetchone()

        if not row:
            return False

        supplied = password_digest(current_password, row[0])
        if not hmac.compare_digest(supplied, row[1]):
            return False

        salt = secrets.token_bytes(16)
        replacement = password_digest(new_password, salt)

        db.execute("""
            UPDATE users
            SET salt=?, password_hash=?
            WHERE id=1 AND enabled=1
        """, (salt, replacement))

        db.execute("DELETE FROM sessions WHERE user_id=1")
        db.execute("DELETE FROM failures")
        db.commit()

    return True


def recover_admin(new_password):
    """Local privileged recovery; revoke all sessions."""
    if not isinstance(new_password, str) or not 12 <= len(new_password) <= 1024:
        raise ValueError("New password must be 12–1024 characters")

    with closing(connect()) as conn, conn as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT id FROM users WHERE id=1"
        ).fetchone()

        if not row:
            raise RuntimeError("Administrator account missing")

        salt = secrets.token_bytes(16)
        hashed = password_digest(new_password, salt)

        db.execute("""
            UPDATE users
            SET salt=?, password_hash=?, enabled=1
            WHERE id=1
        """, (salt, hashed))

        db.execute("DELETE FROM sessions")
        db.execute("DELETE FROM failures")
        db.commit()
