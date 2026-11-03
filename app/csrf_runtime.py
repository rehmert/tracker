"""Per-instance CSRF signing-key storage and cookie preparation.

The key lives outside source control in TRACKER_DATA_DIR.
This module issues tokens; it does not enforce CSRF.
"""

import os
import stat
from pathlib import Path

from . import config
from .csrf_tokens import issue_token, verify_token

COOKIE_NAME = "tracker_csrf_v1"
HEADER_NAME = "X-Tracker-CSRF"
FIELD_NAME = "csrf_token"

KEY_FILENAME = ".tracker-csrf-signing-key-v1"


def key_path():
    return Path(config.DATA_DIR) / KEY_FILENAME


def load_key(path=None):
    """Create once, or validate an existing 0600 regular file.

    Exclusive creation prevents competing workers from
    overwriting an existing signing key.
    """
    path = Path(path) if path is not None else key_path()

    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
    except FileExistsError:
        pass
    else:
        try:
            key = os.urandom(32)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(key)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            try:
                path.unlink()
            except OSError:
                pass
            raise

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)

    with os.fdopen(descriptor, "rb") as stream:
        details = os.fstat(stream.fileno())

        if not stat.S_ISREG(details.st_mode):
            raise ValueError(
                "CSRF key must be a regular file"
            )

        if stat.S_IMODE(details.st_mode) & 0o077:
            raise ValueError(
                "CSRF key permissions must restrict group "
                "and other access"
            )

        key = stream.read(33)

    if len(key) != 32:
        raise ValueError(
            "CSRF key must contain exactly 32 bytes"
        )

    return key


def prepare_html_cookie(request, response):
    """Set or preserve a signed token on successful HTML GET."""
    if request.method != "GET":
        return

    if response.status_code >= 400:
        return

    if not response.headers.get(
        "content-type", ""
    ).lower().startswith("text/html"):
        return

    if request.url.path.startswith("/static/"):
        return

    key = load_key()
    existing = request.cookies.get(COOKIE_NAME)

    if existing and verify_token(existing, key):
        return

    token = issue_token(key)

    response.set_cookie(
        COOKIE_NAME,
        token,
        path="/",
        secure=request.url.scheme == "https",
        httponly=False,
        samesite="strict",
        max_age=60 * 60 * 24 * 30,
    )
