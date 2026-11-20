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
