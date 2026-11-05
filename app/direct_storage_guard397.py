"""Release 397: guard legacy direct-database and backup tools.

These features still access process-wide SQLite and backup
locations. They must remain unavailable to secondary users.

In authenticated session mode:
- Validate the server-side session and administrator identity.
- Match the configured DB URL to the authorized legacy DB.
- Reject symlinked database files and unsafe backup paths.

Legacy Basic Auth remains the application's responsibility
when session authentication is disabled.

This module does not create, migrate, or open user databases.
"""

from pathlib import Path

from fastapi import HTTPException, Request
from sqlalchemy.engine import make_url

from . import backup, config, session_auth385
from .user_db389 import resolve_authenticated_storage


def _no_symlink_components(path: Path):
    """Reject symlink components without modifying the filesystem."""

    candidate = Path(path).absolute()

    for component in (candidate, *candidate.parents):
        if component.is_symlink():
            raise HTTPException(
                503,
                "Symlinked storage path is unsupported",
            )


def require_direct_storage397(request: Request):
    """Authorize use of the legacy SQLite database browser tools."""

    if not session_auth385.enabled():
        return None

    storage = resolve_authenticated_storage(request)

    if storage.user_id != 1 or storage.mode != "legacy-admin":
        raise HTTPException(
            403,
            "Administrator database required",
        )

    expected = Path(storage.database).absolute()

    try:
        url = make_url(config.DB_URL)
    except (ValueError, TypeError):
        raise HTTPException(
            503,
            "Invalid database configuration",
        ) from None

    if url.get_backend_name() != "sqlite":
        raise HTTPException(
            503,
            "SQLite database required",
        )

    database = url.database

    if not database or database == ":memory:":
        raise HTTPException(
            503,
            "File-backed SQLite database required",
        )

    configured = Path(database)

    if not configured.is_absolute():
        configured = (
            Path(config.BASE_DIR).parent / configured
        )

    configured = configured.absolute()

    if configured != expected:
        raise HTTPException(
            503,
            "Direct database configuration mismatch",
        )

    _no_symlink_components(configured)

    if not configured.is_file():
        raise HTTPException(
            503,
            "Authorized database unavailable",
        )

    return None


def require_backup_storage397(request: Request):
    """Authorize legacy whole-database backup operations."""

    require_direct_storage397(request)

    if not session_auth385.enabled():
        return None

    backup_directory = Path(backup.BACKUP_DIR).absolute()

    _no_symlink_components(backup_directory)

    # The backup root may intentionally be outside the
    # data directory. Do not replace its configured location.
    # The existing backup API retains filename validation,
    # archive integrity verification, and restore controls.
    return None
