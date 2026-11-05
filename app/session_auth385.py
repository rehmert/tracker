"""DEV-only single-admin sessions.

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

from . import config

COOKIE = "tracker_session"
FLAG = ".tracker-session-auth-dev"
DATABASE = "tracker-auth.sqlite3"

SESSION_SECONDS = 12 * 3600
REMEMBER_SECONDS = 30 * 86400


def enabled():
    return (
        config.instance_label() == "DEV"
        and (config.DATA_DIR / FLAG).is_file()
    )


def database_path():
    return config.DATA_DIR / DATABASE


def connect():
    path = database_path()

    if not path.is_file() or path.is_symlink():
        raise RuntimeError("Authentication store unavailable")

    db = sqlite3.connect(str(path), timeout=5)
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=5000")
    return db


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

        with sqlite3.connect(str(path)) as db:
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
        with connect() as db:
            db.execute(
                "DELETE FROM failures WHERE occurred_at < ?",
                (now - 900,),
            )

            count = db.execute("""
                SELECT COUNT(*) FROM failures
                WHERE username=? AND occurred_at>=?
            """, (username, now - 900)).fetchone()[0]

            if count >= 8:
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

    with connect() as db:
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
        with connect() as db:
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

    with connect() as db:
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
