"""Read-only release evidence without exposing logs or file paths."""
import json
import os
import stat
import tempfile
from pathlib import Path
from .pk_release_report253 import collect


def report(root):
    data=collect(root,limit=20)
    entries=data['entries']

    return {
        'format':'tracker-release-manifest-v1',
        'count':len(entries),
        'successes':sum(
            e['status']=='success'
            for e in entries
        ),
        'failures':sum(
            e['status']=='failed'
            for e in entries
        ),
        'incomplete':sum(
            e['status']=='incomplete'
            for e in entries
        ),
        'entries':entries
    }


def write_atomic(root,destination):
    root=Path(root)
    destination=Path(destination)

    if destination.parent.resolve()!=root.resolve():
        raise ValueError('Manifest must remain in evidence directory')

    mode=root.stat().st_mode
    if not stat.S_ISDIR(mode):
        raise ValueError('Evidence directory must be a directory')
    if mode & 0o022:
        raise PermissionError('Unsafe evidence directory permissions')

    if destination.is_symlink():
        raise ValueError('Refusing manifest symlink')
    if destination.exists() and not destination.is_file():
        raise ValueError('Manifest destination is not a file')

    content=json.dumps(
        report(root),indent=2,sort_keys=True
    )+'\n'

    fd,temp=tempfile.mkstemp(
        prefix='.tracker-manifest-',
        suffix='.tmp',
        dir=root
    )

    try:
        os.fchmod(fd,0o600)

        with os.fdopen(fd,'w') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

        os.replace(temp,destination)
        os.chmod(destination,0o600)

        dir_fd=os.open(
            str(root),
            os.O_RDONLY|os.O_DIRECTORY
        )
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    finally:
        if os.path.exists(temp):
            os.unlink(temp)

    return destination
