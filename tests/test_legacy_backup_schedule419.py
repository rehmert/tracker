"""Release 419: bounded, read-only host scheduler inventory tests."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/tracker-legacy-backup-schedule-audit419.py'


def load():
    spec = importlib.util.spec_from_file_location('legacy_audit419', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fixture_tree(tmp_path):
    project = tmp_path / 'source'
    host = tmp_path / 'host'
    for d in ('scripts', 'deploy'):
        (project / d).mkdir(parents=True)
    (project / 'scripts/backup.sh').write_text('echo old backup.sh implementation\n')
    (project / 'scripts/replicate_backups.sh').write_text('exec tracker_replica.py\n')
    (project / 'deploy/tracker-backup.service').write_text(
        'ExecStart=python -m scripts.tracker_backup create\n'
    )
    (host / 'etc/cron.d').mkdir(parents=True)
    (host / 'etc/systemd/system').mkdir(parents=True)
    return project, host


def test_repository_verified_unit_is_not_legacy(fixture_tree):
    project, host = fixture_tree
    result = load().build_report(project, host, runtime=False)
    assert result['release'] == 419
    assert result['legacy_references'] == []
    assert any(i['scope'] == 'repository' for i in result['verified_references'])
    assert not result['coverage_complete']
    assert not result['multi_user_enabled']


def test_installed_cron_detects_legacy_with_line(fixture_tree):
    project, host = fixture_tree
    cron = host / 'etc/cron.d/tracker-legacy'
    cron.write_text('# /opt/tracker/scripts/backup.sh commented\n'
                    '15 3 * * * root /opt/tracker/scripts/backup.sh /scratch\n')
    result = load().build_report(project, host, runtime=False)
    assert len(result['legacy_references']) == 1
    item = result['legacy_references'][0]
    assert item['location'] == str(cron)
    assert item['line'] == 2
    assert 'scratch' not in str(item)


def test_host_systemd_execstart_detected(fixture_tree):
    project, host = fixture_tree
    service = host / 'etc/systemd/system/legacy.service'
    service.write_text('Description=Legacy\nExecStart=/bin/bash /opt/tracker/scripts/backup.sh\n')
    result = load().build_report(project, host, runtime=False)
    assert any(i['location'] == str(service) and i['line'] == 2
               for i in result['legacy_references'])


def test_spooled_crontab_is_scanned(fixture_tree):
    project, host = fixture_tree
    spool = host / 'var/spool/cron/crontabs'
    spool.mkdir(parents=True)
    (spool / 'tracker').write_text('0 0 * * * scripts/backup.sh /backup\n')
    result = load().build_report(project, host, runtime=False)
    assert any(i['scope'] == 'installed_cron'
               for i in result['legacy_references'])


def test_symlink_is_skipped_without_reading_target(fixture_tree):
    project, host = fixture_tree
    outside = host / 'secret.txt'
    outside.write_text('0 1 * * * scripts/backup.sh /hidden\n')
    alias = host / 'etc/cron.d/alias'
    alias.symlink_to(outside)
    result = load().build_report(project, host, runtime=False)
    assert not result['legacy_references']
    assert any('Skipped symlink' in w for w in result['warnings'])


def test_systemd_and_crontab_runtime_queries_are_read_only(fixture_tree):
    project, host = fixture_tree
    commands = []

    def fake_runner(argv, **kwargs):
        commands.append(tuple(argv))
        assert kwargs['check'] is False
        if argv[:2] == ['systemctl', 'is-active']:
            return subprocess.CompletedProcess(argv, 0, 'active\n', '')
        if argv[:2] == ['systemctl', 'is-enabled']:
            return subprocess.CompletedProcess(argv, 0, 'enabled\n', '')
        if argv[:2] == ['systemctl', 'show']:
            return subprocess.CompletedProcess(
                argv, 0, '{ path=/opt/tracker/scripts/backup.sh }\n', ''
            )
        return subprocess.CompletedProcess(
            argv, 0, '12 2 * * * /opt/tracker/scripts/backup.sh SECRET=do-not-print\n', ''
        )

    result = load().build_report(project, host, runner=fake_runner)
    assert result['timer']['is-active'] == 'active'
    assert result['timer']['is-enabled'] == 'enabled'
    assert any(i['scope'] == 'systemd_runtime' for i in result['legacy_references'])
    assert any(i['scope'] == 'crontab_runtime' for i in result['legacy_references'])
    assert 'do-not-print' not in json.dumps(result)
    assert all(c[0] in ('systemctl', 'crontab') for c in commands)


def test_failed_commands_mark_incomplete_without_false_clean(fixture_tree):
    project, host = fixture_tree

    def failed(argv, **kwargs):
        if argv[0] == 'crontab':
            raise FileNotFoundError('crontab')
        return subprocess.CompletedProcess(argv, 1, '', 'error')

    result = load().build_report(project, host, runner=failed)
    assert result['warnings']
    assert result['timer']['is-active'] == 'unknown'
    assert result['coverage_complete'] is False


def test_no_crontab_is_not_an_error(fixture_tree):
    project, host = fixture_tree

    def runner(argv, **kwargs):
        if argv[0] == 'crontab':
            return subprocess.CompletedProcess(argv, 1, '', 'no crontab for tracker')
        return subprocess.CompletedProcess(argv, 0, 'inactive', '')

    result = load().build_report(project, host, runner=runner)
    assert not any('crontab query incomplete' in x for x in result['warnings'])


def test_bounded_file_size_is_reported(fixture_tree):
    project, host = fixture_tree
    huge = host / 'etc/cron.d/huge'
    huge.write_bytes(b'A' * 262145)
    result = load().build_report(project, host, runtime=False)
    assert any('Oversized file' in x for x in result['warnings'])
    assert result['coverage_complete'] is False


def test_json_cli_does_not_need_application_imports():
    result = subprocess.run(
        [sys.executable, '-I', str(SCRIPT), '--json'],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    item = json.loads(result.stdout)
    assert item['release'] == 419
    assert item['coverage_complete'] is False
    assert item['multi_user_enabled'] is False
