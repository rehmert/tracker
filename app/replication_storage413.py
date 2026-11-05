"""Read-only, fail-closed preflight for administrator backup replication.

This validates the current administrator whole-instance context and the
secondary local archive directory. It never opens archive contents,
copies a file, writes a receipt, or prunes any backup.

This does not enable secondary-user storage or provide authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from .background_storage410 import administrator_context410


@dataclass(frozen=True)
class AdministratorReplicationContext:
    user_id: int
    scope: str
    data_dir: Path
    database: Path
    primary: Path
    secondary: Path


def _no_symlink_components(path: Path) -> Path:
    candidate = Path(path).absolute()
    for component in (candidate, *candidate.parents):
        if component.is_symlink():
            raise ValueError(
                "Symlinked replication storage path is forbidden"
            )
    return candidate


def administrator_replication_context413(
    destination: Path | str | None = None, *, user_id: int = 1,
) -> AdministratorReplicationContext:
    """Inspect the configured admin source and replica without writes.

    This only checks the administrator whole-instance archive.
    The existing manual --source mode is not authorized by it.
    """
    admin = administrator_context410(user_id=user_id)
    primary = _no_symlink_components(admin.backup_dir)

    if not primary.is_dir():
        raise ValueError(
            "Administrator backup directory is unavailable"
        )

    configured = (
        destination if destination is not None
        else os.getenv(
            "TRACKER_BACKUP_REPLICA_DIR", "/tracker-backups"
        )
    )

    if not configured or not Path(configured).is_absolute():
        raise ValueError(
            "Replica destination must be an absolute path"
        )

    secondary = _no_symlink_components(Path(configured))
    if not secondary.is_dir():
        raise ValueError(
            "Replica destination must already be a directory"
        )

    if (
        primary == secondary
        or primary in secondary.parents
        or secondary in primary.parents
    ):
        raise ValueError(
            "Primary and replica directories overlap"
        )

    if (
        secondary == admin.data_dir
        or secondary in admin.data_dir.parents
        or admin.data_dir in secondary.parents
    ):
        raise ValueError(
            "Replica destination overlaps live data"
        )

    return AdministratorReplicationContext(
        user_id=1,
        scope="legacy-admin-instance",
        data_dir=admin.data_dir,
        database=admin.database,
        primary=primary,
        secondary=secondary,
    )
