"""Cooperative cross-process upload-file lock.

The backup reader and central upload writer/deleter share this lock.
It does not provide atomicity with database commits or third-party writes.
"""
import asyncio
import fcntl
import os
import stat
import time

from contextlib import asynccontextmanager, contextmanager
from pathlib import Path


def _file(data_dir):
    root = Path(data_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    flags = (
        os.O_RDONLY
        | os.O_CREAT
        | getattr(os, 'O_NOFOLLOW', 0)
    )

    fd = os.open(
        root / '.tracker-upload-snapshot.lock',
        flags,
        0o644
    )

    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Invalid upload lock file')

        # Also readable when a root-run backup created the file.
        try:
            os.fchmod(fd, 0o644)
        except PermissionError:
            pass
    except BaseException:
        os.close(fd)
        raise

    return fd


def _attempt(fd):
    try:
        fcntl.flock(
            fd,
            fcntl.LOCK_EX | fcntl.LOCK_NB
        )
        return True
    except BlockingIOError:
        return False


@contextmanager
def upload_guard(data_dir, timeout=30.0):
    fd = _file(data_dir)
    deadline = time.monotonic() + timeout

    try:
        while not _attempt(fd):
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    'Upload snapshot lock busy'
                )
            time.sleep(.05)

        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@asynccontextmanager
async def async_upload_guard(data_dir, timeout=30.0):
    fd = _file(data_dir)
    deadline = time.monotonic() + timeout

    try:
        while not _attempt(fd):
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    'Upload snapshot lock busy'
                )
            await asyncio.sleep(.05)

        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
