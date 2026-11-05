"""Read-only path validation for opt-in administrator SQLite maintenance.

This validates paths before CLI database reads or output creation.
It does not grant user permission or enable secondary account storage.
"""
from pathlib import Path

from .background_storage410 import administrator_context410


def _checked_absolute(path):
    candidate = Path(path)
    if not candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(
            "Scoped maintenance requires absolute paths without traversal"
        )
    candidate = candidate.absolute()

    for component in (candidate, *candidate.parents):
        if component.is_symlink():
            raise ValueError(
                "Symlinked maintenance path is forbidden"
            )
    return candidate


def scoped_paths416(requested_database=None, output_path=None):
    """Return validated administrator DB and optional fresh output file path."""
    context = administrator_context410()

    if requested_database is not None:
        requested = _checked_absolute(requested_database)
        if requested != context.database:
            raise ValueError(
                "Database does not match administrator storage"
            )

    destination = None

    if output_path is not None:
        destination = _checked_absolute(output_path)

        if (
            destination == context.data_dir
            or context.data_dir in destination.parents
            or destination == context.backup_dir
            or context.backup_dir in destination.parents
        ):
            raise ValueError(
                "Scoped maintenance output overlaps protected storage"
            )

        if destination.exists():
            raise FileExistsError(
                "Scoped maintenance refuses to overwrite output"
            )

        if not destination.parent.is_dir():
            raise ValueError(
                "Scoped maintenance output directory must already exist"
            )

    return context.database, destination
