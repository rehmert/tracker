"""Release 399: fail-closed, verified workspace selection.

This module is the future common boundary for database and
attachment operations. In this release it authorizes only
the existing administrator.

It never provisions storage, opens a secondary database,
creates accounts, migrates files, or enables new users.

Callers must use an authenticated Request, never a user ID
supplied by a URL, form, query string, or request header.
"""

from pathlib import Path

from fastapi import HTTPException, Request

from . import config
from .request_scope393 import verified_request_scope
from .user_db389 import resolve_authenticated_storage
from .user_storage388 import planned_storage


def _reject_links399(path):
    """Reject symlinks anywhere in an existing path hierarchy."""
    path = Path(path).absolute()

    for component in (path, *path.parents):
        if component.is_symlink():
            raise HTTPException(
                503, "Symlinked user storage is unsupported"
            )


def authenticated_workspace399(request: Request):
    """Return administrator storage after independently verified checks.

    Future-user storage cannot be returned by this function
    until a separately reviewed activation implementation
    replaces its explicit administrator-only rule.
    """
    scope = verified_request_scope(request)
    storage = resolve_authenticated_storage(request)

    if (
        scope.user_id != 1
        or storage.user_id != 1
        or storage.mode != "legacy-admin"
        or scope.storage != storage
    ):
        raise HTTPException(
            403, "Authenticated workspace mismatch"
        )

    expected = planned_storage(1)

    if storage != expected:
        raise HTTPException(
            503, "Workspace configuration mismatch"
        )

    if Path(config.DB_PATH).absolute() != expected.database:
        raise HTTPException(
            503, "Workspace database path mismatch"
        )

    if (
        Path(config.UPLOAD_DIR).absolute() != expected.coa
        or Path(config.LAB_DIR).absolute() != expected.labs
    ):
        raise HTTPException(
            503, "Workspace attachment path mismatch"
        )

    for path in (
        storage.root,
        storage.database,
        storage.coa,
        storage.labs,
    ):
        _reject_links399(path)

    if not storage.database.is_file():
        raise HTTPException(
            503, "Authorized workspace database unavailable"
        )

    return storage


def authorized_attachment_dir399(
    request: Request,
    kind: str,
):
    """Select the current user's approved attachment directory.

    Only the two known attachment kinds are allowed.
    No paths or user IDs are accepted from the caller.
    """
    workspace = authenticated_workspace399(request)

    if kind == "coa":
        directory = workspace.coa
    elif kind == "labs":
        directory = workspace.labs
    else:
        raise HTTPException(
            400, "Unsupported attachment category"
        )

    _reject_links399(directory)

    if not directory.is_dir():
        raise HTTPException(
            503, "Attachment directory unavailable"
        )

    return directory


def authorized_attachment_file399(
    request: Request,
    kind: str,
    stored_name: str,
):
    """Resolve only a safe filename under an authorized directory.

    This function does not check database-record ownership.
    The future file-download route must first load the
    record through the current user's scoped database.
    """
    if (
        not isinstance(stored_name, str)
        or not stored_name
        or stored_name in (".", "..")
        or "/" in stored_name
        or "\\" in stored_name
        or "\x00" in stored_name
    ):
        raise HTTPException(
            400, "Invalid stored attachment name"
        )

    directory = authorized_attachment_dir399(
        request, kind
    )

    candidate = directory / stored_name

    _reject_links399(candidate)

    if candidate.parent != directory:
        raise HTTPException(
            403, "Attachment path escapes workspace"
        )

    return candidate
