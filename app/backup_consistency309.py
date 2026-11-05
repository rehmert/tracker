"""Detect upload creation, deletion, replacement, or mutation during backup.

This provides a fail-closed consistency check, not a filesystem-wide
atomic snapshot. Upload writers should ultimately use a shared
snapshot lock.
"""
from pathlib import Path


def upload_inventory(root):
    root=Path(root)

    if root.is_symlink():
        raise ValueError(
            'Uploads directory must not be a symlink'
        )

    if not root.exists():
        return {}

    if not root.is_dir():
        raise ValueError(
            'Uploads path is not a directory'
        )

    inventory={}

    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError(
                f'Uploads must not contain symlinks: {path}'
            )

        if path.is_file():
            stat=path.stat()
            inventory[path.relative_to(root).as_posix()]=(
                stat.st_dev,
                stat.st_ino,
                stat.st_size,
                stat.st_mtime_ns
            )

    return inventory
