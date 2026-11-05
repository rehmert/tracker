"""Authenticated attachment boundary for Labs and COAs.

Administrator user 1 retains legacy locations.
Additional users remain disabled.

Router-level authentication and workspace guards run before
endpoint execution. This helper validates path selection
and stored filenames before filesystem operations.
"""

from pathlib import Path

from fastapi import HTTPException, Request

from . import config, session_auth385
from .user_storage388 import planned_storage
from .workspace_boundary399 import (
    authenticated_workspace399,
    _reject_links399,
)


def require_attachment_workspace400(request: Request):
    """Validate the request's server-verified workspace."""

    if not session_auth385.enabled():
        return None

    workspace = authenticated_workspace399(request)

    if (
        workspace.user_id != 1
        or workspace.mode != "legacy-admin"
    ):
        raise HTTPException(
            403, "Administrator workspace required"
        )

    attachment_directory400("coa")
    attachment_directory400("labs")

    return None


def attachment_directory400(kind: str) -> Path:
    """Resolve a known attachment category, never a client path."""

    if kind == "coa":
        directory = Path(config.UPLOAD_DIR).absolute()
    elif kind == "labs":
        directory = Path(config.LAB_DIR).absolute()
    else:
        raise HTTPException(
            400, "Unsupported attachment category"
        )

    if session_auth385.enabled():
        expected = planned_storage(1)

        target = (
            expected.coa if kind == "coa"
            else expected.labs
        )

        if directory != target:
            raise HTTPException(
                503,
                "Attachment directory configuration mismatch",
            )

    _reject_links399(directory)

    if not directory.is_dir():
        raise HTTPException(
            503, "Attachment directory unavailable"
        )

    return directory


def attachment_file400(kind: str, stored_name: str) -> Path:
    """Resolve one safe stored filename beneath its workspace."""

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

    directory = attachment_directory400(kind)
    candidate = directory / stored_name

    _reject_links399(candidate)

    if candidate.parent != directory:
        raise HTTPException(
            403, "Attachment path escapes workspace"
        )

    return candidate
