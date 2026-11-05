import asyncio
import sqlite3

import pytest

from app.backup import create_backup, verify_backup
from app.upload_coordination325 import (
    upload_guard,
    async_upload_guard
)


def test_cross_descriptor_lock_is_exclusive(tmp_path):
    with upload_guard(tmp_path):
        with pytest.raises(TimeoutError):
            with upload_guard(tmp_path, timeout=.1):
                raise AssertionError(
                    'Lock must not be reentrant'
                )

    with upload_guard(tmp_path, timeout=.1):
        pass


def test_async_writer_waits_for_backup_lock(tmp_path):
    async def check():
        with upload_guard(tmp_path):
            with pytest.raises(TimeoutError):
                async with async_upload_guard(
                    tmp_path,
                    timeout=.1
                ):
                    raise AssertionError(
                        'Concurrent writer entered'
                    )

        async with async_upload_guard(
            tmp_path,
            timeout=.1
        ):
            pass

    asyncio.run(check())


def test_backup_creates_valid_archive_with_guard(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()

    with sqlite3.connect(data / 'tracker.db') as conn:
        conn.execute(
            'CREATE TABLE checked (id INTEGER)'
        )

    archive = create_backup(
        data,
        tmp_path / 'backups'
    )

    assert 'tracker.db' in verify_backup(
        archive
    )['files']
