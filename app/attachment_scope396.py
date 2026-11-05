"""Release 396: authorized Labs and COA attachment boundary.

The existing administrator retains the original database
and attachment directories. Other users remain disabled.

This module does not provision files, create directories,
or permit per-user storage switching.
"""

from pathlib import Path

from fastapi import HTTPException, Request

from . import config, session_auth385
from .user_db389 import resolve_authenticated_storage


def require_attachment_scope396(request: Request):
    """Authorize both database identity and attachment paths."""

    if not session_auth385.enabled():
        # Existing application-level Basic Auth remains
        # responsible in legacy mode. Preserve test fixtures.
        return None

    storage = resolve_authenticated_storage(request)

    if storage.user_id != 1 or storage.mode != "legacy-admin":
        raise HTTPException(
            403, "Administrator storage required"
        )

    expected_coa = Path(storage.coa).absolute()
    expected_labs = Path(storage.labs).absolute()

    configured_coa = Path(config.UPLOAD_DIR).absolute()
    configured_labs = Path(config.LAB_DIR).absolute()

    if (
        configured_coa != expected_coa
        or configured_labs != expected_labs
    ):
        raise HTTPException(
            503, "Attachment storage configuration mismatch"
        )

    # Reject a redirected attachment directory. We do not
    # silently follow symlinks to another user's files.
    for path in (
        configured_coa,
        configured_labs,
    ):
        if path.is_symlink():
            raise HTTPException(
                503, "Symlinked attachment directory unsupported"
            )

    return None
