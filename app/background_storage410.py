"""Release 410: validated, administrator-only background storage context.

No files or directories are created by this module.
No database connection is opened.
No backup, restore, or replication operation is performed.

Secondary-user background contexts are deliberately disabled.
"""

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import make_url

from . import backup, config


@dataclass(frozen=True)
class BackgroundStorageContext:
    user_id: int
    scope: str
    data_dir: Path
    database: Path
    backup_dir: Path


def _check_path(path):
    """Reject symlinks in every existing path component."""
    candidate = Path(path).absolute()

    for component in (candidate, *candidate.parents):
        if component.is_symlink():
            raise ValueError(
                "Symlinked background storage path unsupported"
            )

    return candidate


def administrator_context410(user_id=1):
    """Validate currently configured whole-instance storage.

    This context is not a permission grant. Callers must
    already have authority to run administrator jobs.
    """
    if type(user_id) is not int or user_id != 1:
        raise PermissionError(
            "Secondary-user background storage is disabled"
        )

    data = _check_path(config.DATA_DIR)
    database = _check_path(config.DB_PATH)
    archives = _check_path(backup.BACKUP_DIR)

    if not data.is_dir():
        raise ValueError(
            "Configured administrator data directory is missing"
        )

    if database != data / "tracker.db":
        raise ValueError(
            "Database path does not match administrator data root"
        )

    try:
        url = make_url(config.DB_URL)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Invalid configured database URL"
        ) from exc

    if url.get_backend_name() != "sqlite":
        raise ValueError("SQLite storage is required")

    if not url.database or url.database == ":memory:":
        raise ValueError(
            "File-backed administrator database required"
        )

    configured = Path(url.database)

    if not configured.is_absolute():
        configured = (
            Path(config.BASE_DIR).parent / configured
        )

    configured = _check_path(configured)

    if configured != database:
        raise ValueError(
            "Database URL does not match administrator database"
        )

    if not database.is_file():
        raise ValueError(
            "Administrator database is unavailable"
        )

    if archives.exists() and not archives.is_dir():
        raise ValueError(
            "Configured backup location is not a directory"
        )

    return BackgroundStorageContext(
        user_id=1,
        scope="legacy-admin-instance",
        data_dir=data,
        database=database,
        backup_dir=archives,
    )
