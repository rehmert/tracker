"""Release 417: verified snapshot publish and race preservation."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app import backup, config, maintenance_storage417 as publisher
from scripts import tracker_db_maintenance as cli

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def configured(tmp_path, monkeypatch):
    data = tmp_path / 'data'
    data.mkdir()

    db = data / 'tracker.db'

    with sqlite3.connect(db) as connection:
        connection.execute(
            'CREATE TABLE sample(label TEXT)'
        )
        connection.execute(
            'INSERT INTO sample VALUES (?)',
            ('ADMIN417',),
        )

    archives = tmp_path / 'archives'
    archives.mkdir()

    monkeypatch.setattr(config, 'DATA_DIR', data)
    monkeypatch.setattr(config, 'DB_PATH', db)
    monkeypatch.setattr(
        config,
        'DB_URL',
        f'sqlite:///{db}',
    )
    monkeypatch.setattr(
        backup,
        'BACKUP_DIR',
        archives,
    )

    return data, db, archives


def invoke(monkeypatch, *args):
    monkeypatch.setattr(
        sys,
        'argv',
        ['tracker_db_maintenance.py', *args],
    )
    return cli.main()


def test_scoped_snapshot_is_verified_and_published(
    configured, monkeypatch, tmp_path, capsys
):
    _, db, _ = configured
    target = tmp_path / 'admin-snapshot.db'
    before = db.read_bytes()

    assert invoke(
        monkeypatch,
        'snapshot',
        '--admin-scoped',
        '--output',
        str(target),
    ) == 0

    assert json.loads(
        capsys.readouterr().out
    )['structural_integrity']

    with sqlite3.connect(target) as connection:
        assert connection.execute(
            'SELECT label FROM sample'
        ).fetchone()[0] == 'ADMIN417'

    assert db.read_bytes() == before
    assert not list(
        tmp_path.glob('.tracker-scoped-snapshot-*')
    )


def test_late_destination_race_never_overwrites(
    configured, monkeypatch, tmp_path
):
    _, db, _ = configured
    target = tmp_path / 'race.db'

    real_link = publisher.os.link

    def racing_link(source, destination, *, follow_symlinks):
        target.write_bytes(
            b'EXISTING-CREATED-DURING-PUBLISH'
        )
        return real_link(
            source,
            destination,
            follow_symlinks=follow_symlinks,
        )

    monkeypatch.setattr(
        publisher.os,
        'link',
        racing_link,
    )

    with pytest.raises(FileExistsError):
        publisher.publish_verified_snapshot417(
            db,
            target,
            cli.snapshot,
        )

    assert target.read_bytes() == (
        b'EXISTING-CREATED-DURING-PUBLISH'
    )
    assert not list(
        tmp_path.glob('.tracker-scoped-snapshot-*')
    )


def test_snapshot_failure_never_publishes_partial(
    configured, tmp_path
):
    _, db, _ = configured
    target = tmp_path / 'partial.db'

    def failed_snapshot(source, temporary):
        Path(temporary).write_bytes(b'PARTIAL')
        raise RuntimeError(
            'simulated verification failure'
        )

    with pytest.raises(
        RuntimeError,
        match='simulated verification',
    ):
        publisher.publish_verified_snapshot417(
            db,
            target,
            failed_snapshot,
        )

    assert not target.exists()
    assert not list(
        tmp_path.glob('.tracker-scoped-snapshot-*')
    )


def test_existing_snapshot_is_preserved_before_work(
    configured, monkeypatch, tmp_path
):
    _, db, _ = configured
    target = tmp_path / 'existing.db'
    target.write_bytes(b'KEEP-ME')

    def forbidden(*args, **kwargs):
        raise AssertionError(
            'Snapshot should not run'
        )

    monkeypatch.setattr(
        cli,
        'snapshot',
        forbidden,
    )

    with pytest.raises(
        FileExistsError,
        match='overwrite',
    ):
        invoke(
            monkeypatch,
            'snapshot',
            '--admin-scoped',
            '--output',
            str(target),
        )

    assert target.read_bytes() == b'KEEP-ME'


def test_changed_admin_configuration_blocks_publication(
    configured, monkeypatch, tmp_path
):
    _, db, _ = configured
    target = tmp_path / 'changed.db'

    def change_config(source, temporary):
        with sqlite3.connect(temporary) as connection:
            connection.execute(
                'CREATE TABLE sample(id INTEGER)'
            )

        monkeypatch.setattr(
            config,
            'DB_URL',
            f'sqlite:///{tmp_path / "wrong.db"}',
        )

        return {'ok': True}

    with pytest.raises(
        ValueError,
        match='does not match',
    ):
        publisher.publish_verified_snapshot417(
            db,
            target,
            change_config,
        )

    assert not target.exists()
    assert not list(
        tmp_path.glob('.tracker-scoped-snapshot-*')
    )


def test_protected_destination_never_written(
    configured, monkeypatch
):
    data, _, archives = configured

    for destination in (
        data / 'unsafe.db',
        archives / 'unsafe.db',
    ):
        with pytest.raises(
            ValueError,
            match='protected storage',
        ):
            invoke(
                monkeypatch,
                'snapshot',
                '--admin-scoped',
                '--output',
                str(destination),
            )

        assert not destination.exists()


def test_unscoped_snapshot_retains_existing_behavior(
    configured, monkeypatch, tmp_path
):
    _, db, _ = configured
    target = tmp_path / 'unscoped.db'

    def forbidden(*args, **kwargs):
        raise AssertionError(
            'Unscoped snapshot must not use scoped publisher'
        )

    monkeypatch.setattr(
        publisher,
        'publish_verified_snapshot417',
        forbidden,
    )

    assert invoke(
        monkeypatch,
        'snapshot',
        '--database',
        str(db),
        '--output',
        str(target),
    ) == 0

    with sqlite3.connect(target) as connection:
        assert connection.execute(
            'SELECT label FROM sample'
        ).fetchone()[0] == 'ADMIN417'


def test_direct_scoped_snapshot_without_pythonpath(
    configured, tmp_path
):
    data, db, archives = configured
    target = tmp_path / 'subprocess.db'

    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env['TRACKER_DATA_DIR'] = str(data)
    env['TRACKER_BACKUP_DIR'] = str(archives)

    result = subprocess.run(
        [
            sys.executable,
            '-I',
            str(
                ROOT
                / 'scripts'
                / 'tracker_db_maintenance.py'
            ),
            'snapshot',
            '--admin-scoped',
            '--output',
            str(target),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=40,
    )

    assert result.returncode == 0, (
        result.stdout,
        result.stderr,
    )

    assert json.loads(
        result.stdout
    )['structural_integrity']

    with sqlite3.connect(target) as connection:
        assert connection.execute(
            'SELECT label FROM sample'
        ).fetchone()[0] == 'ADMIN417'


def test_disabled_secondary_users_stay_denied():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)
