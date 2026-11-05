"""Release 422: administrator-scoped SQLite health and broad-scan override."""

import importlib.util
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app import backup, config
from scripts import check_database_health as health

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def roots(tmp_path, monkeypatch):
    data = tmp_path / 'data'
    data.mkdir()

    database = data / 'tracker.db'

    with sqlite3.connect(database) as db:
        db.execute(
            'CREATE TABLE probe(marker TEXT NOT NULL)'
        )
        db.execute(
            "INSERT INTO probe VALUES ('admin422')"
        )

    archives = tmp_path / 'archives'
    archives.mkdir()

    other = tmp_path / 'other'
    other.mkdir()

    other_db = other / 'other.sqlite3'

    with sqlite3.connect(other_db) as db:
        db.execute(
            'CREATE TABLE probe(marker TEXT NOT NULL)'
        )
        db.execute(
            "INSERT INTO probe VALUES ('outside422')"
        )

    monkeypatch.setattr(config, 'DATA_DIR', data)
    monkeypatch.setattr(config, 'DB_PATH', database)
    monkeypatch.setattr(
        config, 'DB_URL', f'sqlite:///{database}'
    )
    monkeypatch.setattr(
        backup, 'BACKUP_DIR', archives
    )
    monkeypatch.setattr(
        health, 'SEARCH_PATHS', [data, archives, other]
    )

    return data, database, archives, other_db


def load_audit(name):
    path = (
        ROOT / 'scripts'
        / 'tracker-background-entrypoints-audit418.py'
    )
    spec = importlib.util.spec_from_file_location(
        name, path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_checks_only_admin_database(roots, capsys):
    _, database, _, other_db = roots
    before = (
        database.read_bytes(),
        other_db.read_bytes(),
    )

    assert health.main([]) == 0
    output = capsys.readouterr().out

    assert f'Checking: {database}' in output
    assert str(other_db) not in output
    assert 'Databases checked: 1' in output

    assert before == (
        database.read_bytes(),
        other_db.read_bytes(),
    )


def test_invalid_url_blocks_check(roots, monkeypatch, capsys):
    _, database, _, other_db = roots
    monkeypatch.setattr(
        config, 'DB_URL', f'sqlite:///{other_db}'
    )
    monkeypatch.setattr(
        health,
        'check_database',
        lambda path: pytest.fail('Database must not open'),
    )

    assert health.main([]) == 1
    assert 'does not match' in capsys.readouterr().err
    assert database.exists()


def test_cross_workspace_database_rejected(roots, monkeypatch):
    _, _, _, other_db = roots

    monkeypatch.setattr(config, 'DB_PATH', other_db)
    monkeypatch.setattr(
        health,
        'check_database',
        lambda path: pytest.fail('No unvalidated query'),
    )

    assert health.main([]) == 1


def test_symlinked_database_rejected(roots, monkeypatch, capsys):
    data, database, _, _ = roots

    alias = data / 'alias.db'
    alias.symlink_to(database)

    monkeypatch.setattr(config, 'DB_PATH', alias)
    monkeypatch.setattr(
        config, 'DB_URL', f'sqlite:///{alias}'
    )

    assert health.main([]) == 1
    assert 'Symlinked' in capsys.readouterr().err


def test_context_check_never_queries_sqlite(
    roots, monkeypatch, capsys
):
    _, database, _, _ = roots

    monkeypatch.setattr(
        health,
        'check_database',
        lambda path: pytest.fail('No SQLite query allowed'),
    )

    assert health.main(['--context-check']) == 0

    output = capsys.readouterr().out
    assert 'PASS: Administrator database context valid' in output
    assert str(database) in output


def test_explicit_scan_all_runs_legacy_discovery(
    roots, monkeypatch, capsys
):
    _, database, _, other_db = roots

    monkeypatch.setattr(
        health,
        'administrator_database',
        lambda: pytest.fail('Explicit override is independent'),
    )

    assert health.main(['--scan-all']) == 0
    output = capsys.readouterr()

    assert f'Checking: {database}' in output.out
    assert str(other_db) in output.out
    assert 'Databases checked: 2' in output.out
    assert 'not account-scoped' in output.err


def test_empty_explicit_scan_does_not_fallback(
    roots, monkeypatch, tmp_path
):
    monkeypatch.setattr(
        health,
        'SEARCH_PATHS',
        [tmp_path / 'missing'],
    )

    assert health.main(['--scan-all']) == 2


def test_duplicate_discovery_deduplicated(
    roots, monkeypatch
):
    data, database, _, _ = roots

    monkeypatch.setattr(
        health, 'SEARCH_PATHS', [data, data]
    )

    assert health.discover_legacy_databases() == [database]


def test_mutually_exclusive_options(roots):
    with pytest.raises(SystemExit) as caught:
        health.main(['--scan-all', '--context-check'])

    assert caught.value.code == 2


def test_418_audit_keeps_broad_override_review(roots):
    audit = load_audit('audit418_422')
    report = audit.build_report()
    audit.validate(report)

    item = report['entrypoints']['database_health_sweep']

    assert item['classification'] == 'admin_default_broad_opt_in'
    assert item['requires_review']
    assert 'database_health_sweep' in report['review_queue']


def test_418_validator_rejects_false_classification(roots):
    audit = load_audit('audit418_negative422')
    report = audit.build_report()

    report['entrypoints']['database_health_sweep'][
        'classification'
    ] = 'admin_default_only'

    with pytest.raises(RuntimeError, match='override'):
        audit.validate(report)


def test_direct_context_check_without_pythonpath(
    roots, tmp_path
):
    data, database, archives, _ = roots

    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env['TRACKER_DATA_DIR'] = str(data)
    env['TRACKER_BACKUP_DIR'] = str(archives)

    result = subprocess.run(
        [
            sys.executable,
            '-I',
            str(
                ROOT / 'scripts'
                / 'check_database_health.py'
            ),
            '--context-check',
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, (
        result.stdout, result.stderr
    )
    assert str(database) in result.stdout


def test_secondary_accounts_remain_disabled():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)
