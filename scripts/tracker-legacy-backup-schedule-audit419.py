#!/usr/bin/env python3
"""Read-only Release 419 legacy backup scheduler inventory.

Inspect selected repository scripts, installed systemd units and root/tracker
cron locations. Query systemd and crontab without changing their state.
This is a bounded inventory, not proof that no other schedulers exist.
No cron commands, credentials, environment contents or file bodies are shown.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
LEGACY = re.compile(r"(?<![A-Za-z0-9_.-])(?:/opt/tracker/)?(?:scripts/)?backup\.sh(?![A-Za-z0-9_.-])")
CURRENT = re.compile(r"(?:\bscripts\.tracker_backup\b|\btracker_backup\.py\b)")
MAX_FILE_BYTES = 262144
MAX_FILES_PER_ROOT = 5000


def _kind(line):
    if line.lstrip().startswith('#'):
        return None
    if LEGACY.search(line):
        return 'legacy_backup'
    if CURRENT.search(line):
        return 'verified_backup'
    return None


def _record_lines(entries, text, scope, identifier):
    for number, line in enumerate(text.splitlines(), 1):
        kind = _kind(line)
        if kind:
            entries.append({
                'kind': kind,
                'scope': scope,
                'location': identifier,
                'line': number,
            })


def _scan_file(path, scope, entries, warnings):
    try:
        if path.is_symlink():
            warnings.append('Skipped symlink: ' + str(path))
            return False
        if not path.is_file():
            return False
        if path.stat().st_size > MAX_FILE_BYTES:
            warnings.append('Oversized file not inspected: ' + str(path))
            return False
        content = path.read_text(encoding='utf-8', errors='replace')
    except OSError as exc:
        warnings.append('Unable to inspect ' + str(path) + ': ' + type(exc).__name__)
        return False
    _record_lines(entries, content, scope, str(path))
    return True


def _scan_directory(folder, recursive, predicate, scope, entries, warnings):
    if not folder.exists():
        return 0
    if folder.is_symlink():
        warnings.append('Skipped symlink directory: ' + str(folder))
        return 0
    if not folder.is_dir():
        warnings.append('Not a directory: ' + str(folder))
        return 0
    try:
        paths = sorted(folder.rglob('*') if recursive else folder.iterdir())
    except OSError as exc:
        warnings.append('Cannot list ' + str(folder) + ': ' + type(exc).__name__)
        return 0
    if len(paths) > MAX_FILES_PER_ROOT:
        warnings.append('Directory scan truncated: ' + str(folder))
        paths = paths[:MAX_FILES_PER_ROOT]
    total = 0
    for path in paths:
        if predicate(path):
            total += int(_scan_file(path, scope, entries, warnings))
    return total


def _command(argv, runner):
    try:
        return runner(argv, capture_output=True, text=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return exc


def build_report(project=PROJECT, host=Path('/'), runner=subprocess.run, runtime=True):
    project = Path(project)
    host = Path(host)
    entries = []
    warnings = []
    counts = {}

    scripts = project / 'scripts'
    deploy = project / 'deploy'
    counts['repository_wrappers'] = _scan_directory(
        scripts, False,
        lambda p: p.suffix == '.sh' and p.name != 'backup.sh',
        'repository', entries, warnings,
    )
    counts['repository_units'] = _scan_directory(
        deploy, False,
        lambda p: p.suffix in ('.service', '.timer', '.path'),
        'repository', entries, warnings,
    )

    cron_files = [
        host / 'etc/crontab',
        *[host / f'var/spool/cron/crontabs/{account}' for account in ('root', 'tracker')],
        *[host / f'var/spool/cron/{account}' for account in ('root', 'tracker')],
    ]
    counts['cron_files'] = sum(
        int(_scan_file(p, 'installed_cron', entries, warnings))
        for p in cron_files
    )

    for name in ('cron.d', 'cron.hourly', 'cron.daily', 'cron.weekly', 'cron.monthly'):
        counts['cron_files'] += _scan_directory(
            host / 'etc' / name, False,
            lambda p: not p.name.startswith('.') and p.is_file(),
            'installed_cron', entries, warnings,
        )

    counts['installed_units'] = 0
    for name in ('etc/systemd/system', 'run/systemd/system',
                 'usr/lib/systemd/system', 'lib/systemd/system'):
        counts['installed_units'] += _scan_directory(
            host / name, True,
            lambda p: p.suffix in ('.service', '.timer', '.path'),
            'installed_systemd', entries, warnings,
        )

    units = {}
    if runtime:
        for command in ('is-active', 'is-enabled'):
            result = _command(['systemctl', command, 'tracker-backup.timer'], runner)
            if isinstance(result, BaseException):
                warnings.append('systemctl ' + command + ' unavailable: '
                                + type(result).__name__)
                units[command] = 'unknown'
            else:
                units[command] = (result.stdout.strip() or 'unknown')[:100]

        result = _command(
            ['systemctl', 'show', 'tracker-backup.service',
             '--property=ExecStart', '--value', '--no-pager'], runner,
        )
        if isinstance(result, BaseException) or result.returncode != 0:
            warnings.append('systemctl ExecStart unavailable')
        else:
            _record_lines(
                entries, result.stdout, 'systemd_runtime',
                'tracker-backup.service:ExecStart',
            )

        for account in ('root', 'tracker'):
            result = _command(['crontab', '-u', account, '-l'], runner)
            if isinstance(result, BaseException):
                warnings.append('crontab query unavailable for ' + account)
            elif result.returncode == 0:
                _record_lines(
                    entries, result.stdout, 'crontab_runtime',
                    'crontab:' + account,
                )
            elif 'no crontab' not in result.stderr.lower():
                warnings.append('crontab query incomplete for ' + account)
    else:
        units = {'is-active': 'not-queried', 'is-enabled': 'not-queried'}

    entries.sort(key=lambda item: (item['scope'], item['location'], item['line']))
    return {
        'release': 419,
        'scope': 'bounded read-only source and installed-scheduler inventory',
        'legacy_references': [r for r in entries if r['kind'] == 'legacy_backup'],
        'verified_references': [r for r in entries if r['kind'] == 'verified_backup'],
        'files_inspected': counts,
        'timer': units,
        'warnings': warnings,
        'coverage_complete': False,
        'multi_user_enabled': False,
        'background_job_isolation_complete': False,
        'note': 'No reference found is not proof of absence: user units, containers and external schedulers may exist.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print('=== RELEASE 419 LEGACY BACKUP SCHEDULER INVENTORY ===')
        print('Legacy backup references:', len(report['legacy_references']))
        for found in report['legacy_references']:
            print('REVIEW:', found['scope'], found['location'], 'line', found['line'])
        print('Verified backup references:', len(report['verified_references']))
        print('tracker-backup.timer: active=', report['timer']['is-active'],
              'enabled=', report['timer']['is-enabled'])
        print('Inspected files:', report['files_inspected'])
        print('Inspection warnings:', len(report['warnings']))
        for warning in report['warnings'][:20]:
            print('WARNING:', warning)
        print('Coverage: LIMITED; no conclusion of legacy retirement')
        print('Secondary users: DISABLED')
        print('PASS: Read-only inventory completed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
