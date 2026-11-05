"""Release 420: legacy updater retirement and truthful scheduler inventory."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/tracker-legacy-backup-schedule-audit419.py'
UPDATER = ROOT / 'scripts/update.sh'


def audit_module():
    spec = importlib.util.spec_from_file_location('audit420', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stub_tree(tmp_path):
    project = tmp_path / 'source'
    host = tmp_path / 'host'
    (project / 'scripts').mkdir(parents=True)
    (project / 'deploy').mkdir()
    (host / 'etc/systemd/system').mkdir(parents=True)
    (host / 'etc/cron.d').mkdir(parents=True)
    (project / 'scripts/update.sh').write_text(UPDATER.read_text())
    (project / 'deploy/tracker-backup.service').write_text(
        'ExecStart=/opt/tracker/.venv/bin/python -m scripts.tracker_backup create\n'
    )
    return project, host


def test_retired_updater_refuses_execution_without_writing(tmp_path):
    marker = tmp_path / 'sentinel'
    marker.write_bytes(b'keep')

    result = subprocess.run(
        ['sh', str(UPDATER)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 2
    assert 'retired' in result.stderr
    assert 'tracker-release.sh' in result.stderr
    assert marker.read_bytes() == b'keep'


def test_unsafe_updater_steps_are_absent():
    source = UPDATER.read_text()

    for forbidden in (
        'git pull',
        'pip install',
        'systemctl restart',
        'sqlite3 ',
        'tar -czf',
        'sudo ',
    ):
        assert forbidden not in source

    assert source.endswith('exit 2\n')


def test_repository_updater_no_longer_references_legacy_backup(tmp_path):
    project, host = stub_tree(tmp_path)
    result = audit_module().build_report(project, host, runtime=False)

    assert not result['legacy_references']
    assert result['verified_references']
    assert result['coverage_complete'] is False


def test_systemd_unit_alias_skips_are_counted_separately(tmp_path):
    project, host = stub_tree(tmp_path)
    target = host / 'etc/systemd/system/real.service'
    target.write_text('Description=unit\n')

    alias = host / 'etc/systemd/system/alias.service'
    alias.symlink_to(target)

    report = audit_module().build_report(project, host, runtime=False)

    assert report['systemd_symlinks_skipped'] == 1
    assert not any(
        'Skipped symlink:' in w
        for w in report['warnings']
    )
    assert report['coverage_complete'] is False


def test_cron_symlink_remains_actionable_warning(tmp_path):
    project, host = stub_tree(tmp_path)
    target = host / 'elsewhere'
    target.write_text(
        '0 2 * * * /opt/tracker/scripts/backup.sh /outside\n'
    )

    alias = host / 'etc/cron.d/schedule'
    alias.symlink_to(target)

    report = audit_module().build_report(project, host, runtime=False)

    assert any(
        'Skipped symlink:' in w
        for w in report['warnings']
    )
    assert report['systemd_symlinks_skipped'] == 0
    assert not report['legacy_references']


def test_actual_cron_legacy_reference_remains_visible(tmp_path):
    project, host = stub_tree(tmp_path)
    cron = host / 'etc/cron.d/legacy'
    cron.write_text(
        '30 3 * * * root /opt/tracker/scripts/backup.sh /backups\n'
    )

    report = audit_module().build_report(project, host, runtime=False)

    assert len(report['legacy_references']) == 1
    assert report['legacy_references'][0]['location'] == str(cron)


def test_oversized_scheduler_file_remains_warning(tmp_path):
    project, host = stub_tree(tmp_path)
    (host / 'etc/cron.d/huge').write_bytes(b'x' * 262145)

    report = audit_module().build_report(project, host, runtime=False)

    assert any(
        'Oversized file' in w
        for w in report['warnings']
    )


def test_retirement_does_not_change_verified_service_source():
    source = (ROOT / 'deploy/tracker-backup.service').read_text()

    assert '-m scripts.tracker_backup create' in source
    assert 'scripts/backup.sh' not in source


def test_secondary_accounts_remain_denied():
    from app.user_storage388 import live_storage_for

    for user_id in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)


def test_retired_updater_has_valid_sh_syntax():
    result = subprocess.run(
        ['sh', '-n', str(UPDATER)],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
