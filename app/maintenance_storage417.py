"""Verified SQLite snapshot publication for opt-in administrator maintenance.

Snapshot into a private sibling directory first. Publish only a verified
snapshot using a same-filesystem hard link, which cannot overwrite a name
created concurrently. No unlink is ever performed on the requested target.
"""
import os
import tempfile
from pathlib import Path

from .maintenance_storage416 import scoped_paths416


def publish_verified_snapshot417(database, destination, create_snapshot):
    """Create a verified administrator snapshot without replacing any target."""
    source, target = scoped_paths416(
        requested_database=database,
        output_path=destination,
    )

    with tempfile.TemporaryDirectory(
        prefix=".tracker-scoped-snapshot-",
        dir=target.parent,
    ) as folder:
        temporary = Path(folder) / "snapshot.db"

        result = create_snapshot(source, temporary)

        # Recheck configuration and symlink components before publishing.
        second_source, second_target = scoped_paths416(
            requested_database=database,
            output_path=destination,
        )

        if second_source != source or second_target != target:
            raise ValueError(
                "Scoped maintenance context changed during snapshot"
            )

        # Atomic no-replace publication. FileExistsError also protects
        # against a new destination arriving AFTER the preceding check.
        os.link(
            temporary,
            target,
            follow_symlinks=False,
        )

        return result
