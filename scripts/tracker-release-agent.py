#!/usr/bin/env python3
"""DEV-owned, one-command-at-a-time Tracker release agent.

Poll a GitHub Git ref for an immutable request ID; execute only the next
approved stage and publish sanitized receipts to a separate Git branch.
No application data or raw deployment log is ever published.
"""
from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

APP = Path('/opt/tracker')
STATE = Path('/var/lib/tracker-release-agent')
LOGS = Path('/var/log/tracker-release-agent')
REQUEST_REF = 'refs/remotes/origin/tracker-release-requests'
RECEIPT_REF = 'refs/remotes/origin/tracker-release-receipts'
REQUEST_BRANCH = 'tracker-release-requests'
RECEIPT_BRANCH = 'tracker-release-receipts'
COMMAND_PATH = 'control/current.json'
LATEST_PATH = 'receipts/latest.json'
SHA = re.compile(r'[0-9a-f]{40}\Z')
REQUEST_ID = re.compile(r'r[1-9][0-9]{0,5}-[a-z0-9]{8,20}\Z')
RELEASE_BRANCH = re.compile(r'release/([1-9][0-9]{0,5})-[a-z0-9-]+\Z')
MARKER = re.compile(r'^(?:RELEASE_[0-9]{1,6}_(?:SOURCE|QUALIFICATION|SCOPED_BACKEND|SCOPED_BROWSER|IMPACT_PREFLIGHT|EXIT_STATUS|INSTALLED_DEV|DEV_INSTALL|DEV_DEPLOYMENT|PROD_SCOPED)|DEV_CONTROLLED_RELEASE|PROD_(?:DEPLOY_VERIFIED|INSTALLED_COMMIT|APPROVAL_VERIFIED)|PREFLIGHT|PROMOTED_COMMIT|EXIT_STATUS|REMOTE_DEPLOY_EXIT_STATUS|TARGETED_[0-9]{1,6}_[A-Z0-9_]+)=(?:SUCCESS|PASSED|FAILED|UNMODIFIED|PASSED_SCOPED_NO_DEPLOY|0|1|[0-9a-f]{40})$')
TEST_FAIL = re.compile(r'^(?:FAILED|ERROR) (tests/[a-zA-Z0-9_./-]+)')
COUNTS = re.compile(r'\b([0-9]{1,6} passed(?:, [0-9]{1,6} (?:failed|skipped|warning|warnings|error|errors))*) in [0-9.]+s\b')
ACTION_PREVIOUS = {
    'qualify': None,
    'dev_install': 'qualify',
    'prod_preflight': 'dev_install',
    'prod_deploy': 'prod_preflight',
}


class GateError(Exception):
    pass


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def git(*args: str, input_bytes: bytes | None = None, env: dict | None = None) -> bytes:
    proc = subprocess.run(
        ['git', '-c', f'safe.directory={APP}', '-C', str(APP), *args],
        input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, check=False, timeout=90,
    )
    if proc.returncode:
        # Avoid accidentally leaking remote origin credentials or URL into logs.
        raise GateError(f'Git {args[0]} failed (status {proc.returncode})')
    return proc.stdout


def fetch(branch: str) -> None:
    git('fetch', '--no-tags', 'origin',
        f'refs/heads/{branch}:refs/remotes/origin/{branch}')


def show(ref: str, path: str) -> bytes | None:
    proc = subprocess.run(
        ['git', '-c', f'safe.directory={APP}', '-C', str(APP),
         'show', f'{ref}:{path}'], capture_output=True, timeout=30,
    )
    if proc.returncode:
        return None
    return proc.stdout


def json_read(data: bytes | None) -> dict | None:
    if not data:
        return None
    value = json.loads(data)
    if not isinstance(value, dict):
        raise GateError('Expected JSON object')
    return value


def clean_main(expected: str) -> None:
    if git('branch', '--show-current').decode().strip() != 'main':
        raise GateError('Installed DEV is not on main')
    if git('status', '--porcelain'):
        raise GateError('Installed DEV source is dirty')
    if git('rev-parse', 'HEAD').decode().strip() != expected:
        raise GateError('Installed DEV commit does not match required source')
    status = subprocess.run(['systemctl', 'is-active', '--quiet', 'tracker'], check=False)
    if status.returncode:
        raise GateError('Tracker service is not active')


def validate_command(value: dict) -> dict:
    keys = {'schema', 'request_id', 'action', 'release', 'target', 'base', 'ref', 'previous_request_id'}
    if set(value) != keys or value.get('schema') != 1:
        raise GateError('Unrecognized request schema')
    req = value['request_id']
    target, base, ref = value['target'], value['base'], value['ref']
    release, action = value['release'], value['action']
    if not isinstance(req, str) or not REQUEST_ID.fullmatch(req):
        raise GateError('Invalid request ID')
    if action not in ACTION_PREVIOUS:
        raise GateError('Unrecognized release action')
    if type(release) is not int or not 1 <= release <= 999999:
        raise GateError('Invalid release number')
    if not isinstance(target, str) or not SHA.fullmatch(target):
        raise GateError('Target must be pinned SHA')
    if not isinstance(base, str) or not SHA.fullmatch(base) or target == base:
        raise GateError('Base must be distinct pinned SHA')
    m = RELEASE_BRANCH.fullmatch(ref) if isinstance(ref, str) else None
    if not m or int(m.group(1)) != release:
        raise GateError('Release branch number mismatch')
    prev = value['previous_request_id']
    if prev is not None and (not isinstance(prev, str) or not REQUEST_ID.fullmatch(prev)):
        raise GateError('Invalid previous request ID')
    if (action == 'qualify') != (prev is None):
        raise GateError('Exactly one prior approved stage required except for qualify')
    return value


def validate_chain(command: dict, latest: dict | None) -> None:
    stage = command['action']
    if stage == 'qualify':
        # A new commit must be requalified after a failure; exact same commit
        # may be deliberately requalified with a new request ID.
        return
    if not latest or latest.get('status') != 'passed':
        raise GateError('Previous stage has not passed')
    for key in ('release', 'target', 'base', 'ref'):
        if latest.get(key) != command[key]:
            raise GateError('Prior receipt does not match current release')
    if latest.get('request_id') != command['previous_request_id']:
        raise GateError('Prior receipt ID mismatch')
    if latest.get('action') != ACTION_PREVIOUS[stage]:
        raise GateError('Stages must advance in order')


def pinned_script(target: str, relative_path: str, folder: Path) -> Path:
    data = show(target, relative_path)
    if not data:
        raise GateError(f'Pinned release lacks {relative_path}')
    expected = git('rev-parse', f'{target}:{relative_path}').decode().strip()
    actual = git('hash-object', '--stdin', input_bytes=data).decode().strip()
    if not SHA.fullmatch(expected) or expected != actual:
        raise GateError('Git object integrity mismatch')
    path = folder / relative_path.rsplit('/', 1)[-1]
    path.write_bytes(data)
    path.chmod(0o700)
    syntax = subprocess.run(['bash', '-n', str(path)], check=False)
    if syntax.returncode:
        raise GateError('Pinned release shell syntax invalid')
    return path


def command_for_stage(command: dict, folder: Path) -> list[str]:
    action = command['action']
    target, base, ref = command['target'], command['base'], command['ref']
    release = command['release']
    fetch(ref)
    if git('rev-parse', f'refs/remotes/origin/{ref}').decode().strip() != target:
        raise GateError('Release branch moved or SHA mismatch')
    git('merge-base', '--is-ancestor', base, target)
    clean_main(base if action in ('qualify', 'dev_install') else target)
    if action == 'qualify':
        worker = pinned_script(target, f'scripts/tracker-qualify{release}.sh', folder)
        return [
            'systemd-run', '--collect', '--wait', '--pipe',
            f'--unit=tracker-ops-qa-{command["request_id"]}',
            '--property=PrivateNetwork=yes', '/bin/bash', str(worker), target,
        ]
    if action == 'dev_install':
        worker = pinned_script(target, f'scripts/tracker-install{release}.sh', folder)
        return ['/bin/bash', str(worker), target]
    runner = APP / 'scripts/tracker_promote568.py'
    if not runner.is_file():
        raise GateError('Installed DEV has no signed promotion runner')
    args = [str(APP / '.venv/bin/python'), str(runner), '--release', str(release),
            '--target', target, '--prod-base', base, '--ref', ref]
    if action == 'prod_deploy':
        args.append('--execute')
    return args


def failure_kind(data: str) -> str:
    if 'RELEASE_604_IMPACT_PREFLIGHT=FAILED' in data:
        return 'AssetImpactPreflight'
    if 'syntax error near' in data or 'unexpected argument' in data:
        return 'ShellSyntax'
    if 'FAILED tests/' in data or '=== FAILURES ===' in data:
        return 'TestAssertion'
    if 'RELEASE_ERROR=' in data or 'REMOTE_FAIL:' in data:
        return 'PromotionOrDeploymentGate'
    if 'Permission denied' in data or 'Connection timed out' in data:
        return 'ConnectivityOrPermission'
    return 'StageCommandError'


def safe_diagnostics(data: str) -> dict:
    markers, failures, counts = [], [], []
    for line in data.splitlines():
        stripped = line.strip()
        if MARKER.fullmatch(stripped) and len(markers) < 45:
            markers.append(stripped)
        match = TEST_FAIL.match(stripped)
        if match and len(failures) < 12:
            failures.append(match.group(1)[:160])
        count = COUNTS.search(stripped)
        if count and len(counts) < 8:
            counts.append(count.group(1))
    return {'markers': markers, 'failed_tests': failures, 'test_counts': counts}


def validate_success(command: dict, output: str) -> None:
    action = command['action']
    target = command['target']
