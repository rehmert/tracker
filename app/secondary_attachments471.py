"""Release 471: verified, read-only private attachments.

The record ID is looked up in the authenticated user's
own read-only SQLite database. A filename or filesystem
location is never accepted from the browser.

This module never writes files, enables account login,
or accesses the administrator's attachment directories.
"""
import hashlib
import os
import re
import stat
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import Response
from sqlalchemy import text

from . import config
from .secondary_orm468 import private_orm468
from .user_storage388 import planned_storage


MAX_BYTES471 = 15 * 1024 * 1024

TABLES471 = {
    "coa": "coas",
    "labs": "lab_reports",
}

MIME471 = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}

STORED_NAME471 = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z"
)

SHA471 = re.compile(r"[0-9a-fA-F]{64}\Z")


def _checked_record471(db, kind, record_id):
    if kind not in TABLES471:
        raise HTTPException(
            404, "Attachment category unavailable"
        )

    if type(record_id) is not int or not (
        1 <= record_id <= 2147483647
    ):
        raise HTTPException(
            404, "Attachment unavailable"
        )

    table = TABLES471[kind]

    # SQL table identifiers come only from this allowlist.
    row = db.execute(
        text(
            "SELECT stored_name,content_type,"
            "size_bytes,sha256 "
            f"FROM {table} WHERE id=:record_id"
        ),
        {"record_id": record_id},
    ).one_or_none()

    if row is None:
        raise HTTPException(
            404, "Attachment unavailable"
        )

    name, content_type, size_bytes, sha256 = row

    if (
        type(name) is not str
        or not STORED_NAME471.fullmatch(name)
        or name in (".", "..")
        or content_type not in MIME471
        or type(size_bytes) is not int
        or not 0 < size_bytes <= MAX_BYTES471
        or type(sha256) is not str
        or not SHA471.fullmatch(sha256)
    ):
        raise HTTPException(
            503, "Attachment metadata invalid"
        )

    return name, content_type, size_bytes, sha256.lower()


def _checked_directory471(scope, kind):
    storage = planned_storage(scope.user_id)

    if (
        scope.user_id <= 1
        or scope.database != storage.database
        or storage.mode != "reserved-inactive"
    ):
        raise HTTPException(
            503, "Attachment workspace mismatch"
        )

    directory = (
        storage.coa if kind == "coa"
        else storage.labs
    )

    # Reject symlinks in all existing ancestor components.
    # The actual file is subsequently opened using
    # O_NOFOLLOW relative to an opened directory.
    for component in (directory, *directory.parents):
        if component.is_symlink():
            raise HTTPException(
                503, "Attachment directory unavailable"
            )

    if not directory.is_dir():
        raise HTTPException(
            503, "Attachment directory unavailable"
        )

    return directory


def _read_file471(directory, name, size_bytes, sha256):
    dir_fd = None
    file_fd = None

    try:
        dir_fd = os.open(
            directory,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW,
        )

        file_fd = os.open(
            name,
            os.O_RDONLY
            | os.O_NOFOLLOW
            | getattr(os, "O_NONBLOCK", 0),
            dir_fd=dir_fd,
        )

        info = os.fstat(file_fd)

        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_size != size_bytes
        ):
            raise RuntimeError(
                "Attachment file mismatch"
            )

        with os.fdopen(file_fd, "rb") as stream:
            file_fd = None
            contents = stream.read(MAX_BYTES471 + 1)

        if (
            len(contents) != size_bytes
            or len(contents) > MAX_BYTES471
            or hashlib.sha256(
                contents
            ).hexdigest() != sha256
        ):
            raise RuntimeError(
                "Attachment integrity mismatch"
            )

        return contents

    except (OSError, RuntimeError):
        raise HTTPException(
            503, "Private attachment unavailable"
        ) from None

    finally:
        if file_fd is not None:
            os.close(file_fd)
        if dir_fd is not None:
            os.close(dir_fd)


def private_attachment471(request, kind, record_id):
    if request.query_params:
        raise HTTPException(
            400, "Unexpected attachment parameters"
        )

    with private_orm468(request) as (scope, db):
        name, mime, size, digest = _checked_record471(
            db, kind, record_id
        )

        directory = _checked_directory471(
            scope, kind
        )

        contents = _read_file471(
            directory, name, size, digest
        )

    extension = MIME471[mime]
    filename = (
        f"tracker-{kind}-{record_id}.{extension}"
    )

    return Response(
        content=contents,
        media_type=mime,
        headers={
            "Content-Disposition":
                f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy":
                "default-src 'none'; sandbox",
        },
    )
