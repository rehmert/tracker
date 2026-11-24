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


def validate_chain(
    command: dict, previous: dict | None, latest: dict | None = None,
) -> None:
    stage = command['action']
    if stage == 'qualify':
        # A new commit must be requalified after a failure; exact same commit
        # may be deliberately requalified with a new request ID.
        return
    # Normally the immutable previous-stage receipt is also latest. Allow a
    # fresh request after an earlier *chain-blocked* attempt of this exact
    # same stage, target and PROD base. That attempt was rejected before
    # command_for_stage/execute, so no live deployment could have started.
    # A failed/unknown/possibly executed stage is never silently retried.
    if latest is not None and latest.get('request_id') != command['previous_request_id']:
        recoverable = (
            latest.get('status') == 'blocked'
            and latest.get('failure_category') == 'StageChainBlocked'
            and all(latest.get(key) == command[key] for key in (
                'action', 'release', 'target', 'base', 'ref',
                'previous_request_id',
            ))
        )
        if not recoverable:
            raise GateError('Latest receipt is not prior success or matching blocked attempt')
    if not previous or previous.get('status') != 'passed':
        raise GateError('Previous stage has not passed')
    # A catch-up PROD promotion may begin from an older *installed PROD*
    # commit than the DEV release's qualification/install base. Verify the
    # same exact release, target, branch and prior stage here; the pinned
    # promotion preflight separately verifies PROD's actual installed base,
    # GitHub main, ancestry, signed DEV evidence and active services.
    for key in ('release', 'target', 'ref'):
        if previous.get(key) != command[key]:
            raise GateError('Prior receipt does not match current release')
    if stage != 'prod_preflight' and previous.get('base') != command['base']:
        raise GateError('Prior receipt base does not match current release')
    if previous.get('request_id') != command['previous_request_id']:
        raise GateError('Prior receipt ID mismatch')
    if previous.get('action') != ACTION_PREVIOUS[stage]:
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


def required_stage_markers(command: dict) -> tuple[str, ...]:
    """Validated, public-safe terminal stage markers for durable receipts.

    Keep this list shared by the execution-success gate and the bounded
    diagnostic publisher. A later burst of TARGETED_* diagnostics must never
    displace the actual qualification / installation result.
    """
    release = command['release']
    action = command['action']
    if action == 'qualify':
        return (f'RELEASE_{release}_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY',
                f'RELEASE_{release}_EXIT_STATUS=0')
    if action == 'dev_install':
        return (f'RELEASE_{release}_DEV_INSTALL=SUCCESS',)
    if action == 'prod_preflight':
        return ('PREFLIGHT=PASSED',)
    if action == 'prod_deploy':
        return ('DEV_CONTROLLED_RELEASE=SUCCESS',
                f'PROD_INSTALLED_COMMIT={command["target"]}')
    raise GateError('Unsupported release stage')


def safe_diagnostics(
    data: str, *, command: dict | None = None, status: str | None = None,
) -> dict:
    """Bounded safe receipt: terminal markers first, diagnostic markers next.

    All candidates must match the existing strict allowlist. Never publish
    raw lines, user data, exception details or arbitrarily long marker lists.
    """
    markers, failures, counts = [], [], []
    seen = set()
    for line in data.splitlines():
        stripped = line.strip()
        if MARKER.fullmatch(stripped) and stripped not in seen:
            seen.add(stripped)
            markers.append(stripped)
        match = TEST_FAIL.match(stripped)
        if match and len(failures) < 12:
            failures.append(match.group(1)[:160])
        count = COUNTS.search(stripped)
        if count and len(counts) < 8:
            counts.append(count.group(1))
    priority = (
        required_stage_markers(command)
        if status == 'passed' and command is not None else ()
    )
    # Execution validation already required every terminal marker verbatim.
    # If a future marker falls outside our safe allowlist, fail closed rather
    # than silently publishing a misleading 'passed' receipt.
    if any(value not in seen for value in priority):
        raise GateError('Validated success marker missing from sanitized receipt')
    ordered = list(priority)
    required = set(priority)
    ordered.extend(marker for marker in markers if marker not in required)
    return {'markers': ordered[:45], 'failed_tests': failures, 'test_counts': counts}


def validate_success(command: dict, output: str) -> None:
    action = command['action']
    target = command['target']
    lines = output.splitlines()
    required = list(required_stage_markers(command))
    if action == 'dev_install':
        clean_main(target)
    elif action == 'prod_preflight':
        required.append('DRY_RUN=PASSED (no approval, push, or deployment performed)')
    for expected in required:
        if expected not in lines:
            raise GateError('Expected success marker missing: ' + expected.split('=', 1)[0])


def atomic_json(path: Path, value: dict) -> None:
    data = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    fd, filename = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(filename, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(filename)


def publish_receipt(receipt: dict) -> None:
    req = receipt['request_id']
    for attempt in range(3):
        fetch(RECEIPT_BRANCH)
        existing = json_read(show(RECEIPT_REF, f'receipts/{req}.json'))
        if existing is not None:
            if existing != receipt:
                raise GateError('Conflicting published receipt for request ID')
            return
        parent = git('rev-parse', RECEIPT_REF).decode().strip()
        with tempfile.TemporaryDirectory(prefix='tracker-index-', dir=STATE) as d:
            env = os.environ.copy()
            env['GIT_INDEX_FILE'] = str(Path(d) / 'index')
            env['GIT_AUTHOR_NAME'] = 'Tracker Release Agent'
            env['GIT_AUTHOR_EMAIL'] = 'tracker-release-agent@localhost'
            env['GIT_COMMITTER_NAME'] = env['GIT_AUTHOR_NAME']
            env['GIT_COMMITTER_EMAIL'] = env['GIT_AUTHOR_EMAIL']
            git('read-tree', parent, env=env)
            data = (json.dumps(receipt, sort_keys=True, indent=2) + '\n').encode()
            blob = git('hash-object', '-w', '--stdin', input_bytes=data, env=env).decode().strip()
            for path in (f'receipts/{req}.json', LATEST_PATH):
                git('update-index', '--add', '--cacheinfo', f'100644,{blob},{path}', env=env)
            tree = git('write-tree', env=env).decode().strip()
            commit = git('commit-tree', tree, '-p', parent, '-m', f'Tracker {req} {receipt["action"]}: {receipt["status"]}', env=env).decode().strip()
        process = subprocess.run(
            ['git', '-c', f'safe.directory={APP}', '-C', str(APP),
             'push', 'origin', f'{commit}:refs/heads/{RECEIPT_BRANCH}'],
            capture_output=True, timeout=90,
        )
        if process.returncode == 0:
            print(f'RELEASE_RECEIPT_PUBLISHED={req}', flush=True)
            return
        time.sleep(1 + attempt)
    raise GateError('Unable to publish receipt (GitHub push rejected)')


def execute(command: dict) -> dict:
    req = command['request_id']
    started = utcnow()
    log_path = LOGS / f'{req}.log'
    output = ''
    code = 1
    status = 'failed'
    failure = ''
    try:
        with tempfile.TemporaryDirectory(prefix=f'{req}-', dir=STATE) as d:
            argv = command_for_stage(command, Path(d))
            with log_path.open('wb') as handle:
                os.chmod(log_path, 0o600)
                handle.write(f'RUN={req} ACTION={command["action"]} STARTED={started}\n'.encode())
                handle.flush()
                proc = subprocess.run(argv, stdout=handle, stderr=subprocess.STDOUT,
                                      check=False, timeout=3000, stdin=subprocess.DEVNULL)
                code = proc.returncode
            output = log_path.read_text(encoding='utf-8', errors='replace')
            if code:
                failure = failure_kind(output)
                raise GateError('Stage command failed with exit code ' + str(code))
            validate_success(command, output)
            status = 'passed'
    except (GateError, OSError, subprocess.TimeoutExpired, subprocess.SubprocessError) as exc:
        if not failure:
            failure = type(exc).__name__
        # Raw error message and full log remain local; only error category goes to GitHub.
        with log_path.open('ab') as handle:
            handle.write(('\nLOCAL_STAGE_ERROR=' + str(exc)[:600] + '\n').encode())
        if not output and log_path.is_file():
            output = log_path.read_text(encoding='utf-8', errors='replace')
    receipt = {
        **command,
        'status': status,
        'exit_code': code,
        'started_at_utc': started,
        'finished_at_utc': utcnow(),
        'failure_category': failure or None,
        **safe_diagnostics(output, command=command, status=status),
    }
    return receipt


def validate_control_transition(previous: dict, current: dict, prior_receipt: dict | None) -> None:
    """Fail closed when a GitHub writer rewinds or overwrites a live request."""
    previous = validate_command(previous)
    current = validate_command(current)
    if previous == current:
        return
    if previous['request_id'] == current['request_id']:
        raise GateError('Request ID reused with changed content')
    if prior_receipt is None:
        raise GateError('Outstanding command has no final immutable receipt')
    if any(prior_receipt.get(key) != previous[key] for key in (
            'schema', 'request_id', 'action', 'release', 'target',
            'base', 'ref', 'previous_request_id')):
        raise GateError('Prior immutable receipt does not match queued command')
    status = prior_receipt.get('status')
    if status == 'passed':
        if prior_receipt.get('exit_code') != 0:
            raise GateError('Passed command receipt has nonzero exit')
        old_index = list(ACTION_PREVIOUS).index(previous['action'])
        if current['action'] == 'qualify':
            if previous['action'] not in ('dev_install', 'prod_deploy'):
                raise GateError('Cannot abandon unfinished release')
            if (current['release'] != previous['release'] + 1
                    or current['base'] != previous['target']):
                raise GateError('Next release must descend from completed target')
            return
        if (old_index + 1 >= len(ACTION_PREVIOUS)
                or current['action'] != list(ACTION_PREVIOUS)[old_index + 1]
                or current['release'] != previous['release']
                or current['target'] != previous['target']
                or current['ref'] != previous['ref']
                or current['previous_request_id'] != previous['request_id']):
            raise GateError('Command rewound or skipped approved stage')
        expected_base = previous['base'] if current['action'] != 'prod_preflight' else None
        if expected_base and current['base'] != expected_base:
            raise GateError('Command changed previously approved stage base')
        return
    # A DEV install can fail after partial deployment. Only a definitive
    # immutable failure with a nonzero exit permits replacing it with a NEW
    # qualification of the same release and base. Verify the installed DEV
    # checkout and running service before allowing the control history forward.
    # Do not allow this recovery for unknown, blocked or PROD stages.
    if status == 'failed' and previous['action'] == 'dev_install':
        if (type(prior_receipt.get('exit_code')) is int
                and prior_receipt['exit_code'] != 0
                and current['action'] == 'qualify'
                and current['release'] == previous['release']
                and current['base'] == previous['base']
                and current['ref'] == previous['ref']
                and current['target'] != previous['target']):
            clean_main(previous['base'])
            return
        raise GateError('Failed DEV install requires a new pinned qualification and intact DEV')

    # Exact recovery of a failed PROD deployment whose *source* was promoted
    # but whose remote pre-install schema guard failed before DB backup or code
    # installation. The failed receipt remains immutable. A distinct release
    # must undergo fresh full stage sequencing and a verified PROD preflight.
    # This one-off exception does not apply to any other failed deployment.
    if (
        status == 'failed' and previous['action'] == 'prod_deploy'
        and previous['release'] == 767
        and previous['request_id'] == 'r767-deploy5d23aaf4'
        and previous['target'] == '5d23aaf4f7e7fa4b54c1d5535a622bdd9e9aac13'
        and previous['base'] == '8c67580611fd945d9ae83f8015f071a24ab6fee5'
        and previous['ref'] == 'release/767-prod-device-schema-guard'
        and prior_receipt.get('exit_code') == 1
        and prior_receipt.get('failure_category') == 'PromotionOrDeploymentGate'
        and 'PROMOTED_COMMIT=5d23aaf4f7e7fa4b54c1d5535a622bdd9e9aac13'
            in prior_receipt.get('markers', [])
        and 'REMOTE_DEPLOY_EXIT_STATUS=1' in prior_receipt.get('markers', [])
        and current['action'] == 'qualify'
        and current['release'] == 768
        and current['base'] == previous['target']
        and current['ref'] == 'release/768-prod-relative-data-path-recovery'
        and current['target'] not in (previous['target'], previous['base'])
        and current['previous_request_id'] is None
    ):
        return
    if status == 'failed' and previous['action'] == 'qualify':
        if (current['action'] == 'qualify'
                and current['release'] == previous['release']
                and current['base'] == previous['base']
                and current['ref'] == previous['ref']
                and current['target'] != previous['target']):
            return
        raise GateError('Failed qualification needs a new pinned target')
    if (status == 'blocked'
            and prior_receipt.get('failure_category') == 'StageChainBlocked'
            and all(current[key] == previous[key] for key in (
                'action', 'release', 'target', 'base', 'ref',
                'previous_request_id'))):
        return
    raise GateError('Unknown or potentially executed command cannot be replaced')


def validate_control_ref_history(state: Path, latest_ref: str) -> None:
    """Check EVERY command-branch commit since the last accepted ref.

    The installed DEV release agent is the enforcement point. The GitHub
    branch itself remains mutable, but an unreviewed rewind cannot be
    silently interpreted as an approved instruction by this controller.
    """
    history_path = state / 'control-history745.json'
    if not SHA.fullmatch(latest_ref):
        raise GateError('Invalid GitHub control ref')
    if not history_path.exists():
        initial = json_read(show(latest_ref, COMMAND_PATH))
        if initial is None:
            raise GateError('Missing control command at initial anchor')
        validate_command(initial)
        atomic_json(history_path, {'ref': latest_ref})
        return
    prior = json_read(history_path.read_bytes())
    previous_ref = prior.get('ref') if prior else None
    if not isinstance(previous_ref, str) or not SHA.fullmatch(previous_ref):
        raise GateError('Corrupt or missing controller history anchor')
    if previous_ref == latest_ref:
        return
    git('merge-base', '--is-ancestor', previous_ref, latest_ref)
    steps = git('rev-list', '--reverse', f'{previous_ref}..{latest_ref}').decode().splitlines()
    if not steps or len(steps) > 128:
        raise GateError('Unexpected control-branch history span')
    old_ref = previous_ref
    for new_ref in steps:
        old_command = json_read(show(old_ref, COMMAND_PATH))
        new_command = json_read(show(new_ref, COMMAND_PATH))
        if old_command is None or new_command is None:
            raise GateError('Command missing in controller branch history')
        old_command = validate_command(old_command)
        new_command = validate_command(new_command)
        if old_command != new_command:
            previous_receipt = json_read(show(
                RECEIPT_REF, f'receipts/{old_command["request_id"]}.json'))
            validate_control_transition(old_command, new_command, previous_receipt)
        old_ref = new_ref
    if old_ref != latest_ref:
        raise GateError('Unverified command history endpoint')
    atomic_json(history_path, {'ref': latest_ref})


def main() -> int:
    if os.geteuid() != 0 or os.uname().nodename.split('.')[0] != 'tracker-dev':
        raise GateError('Release agent may only run as root on tracker-dev')
    os.umask(0o077)
    for path in (STATE, LOGS):
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.is_symlink() or path.stat().st_uid != 0 or path.stat().st_mode & 0o077:
            raise GateError('Unsafe agent state/log directory permissions')
    with (STATE / 'lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pending = STATE / 'pending.json'
        if pending.exists():
            receipt = json.loads(pending.read_text())
            publish_receipt(receipt)
            pending.unlink()
            return 0
        fetch(REQUEST_BRANCH)
        cmd = json_read(show(REQUEST_REF, COMMAND_PATH))
        if cmd is None:
            return 0
        cmd = validate_command(cmd)
        req = cmd['request_id']
        seen = STATE / f'{req}.started'
        fetch(RECEIPT_BRANCH)
        # Release 745: reject stale safety-hold rewinds and pending overwrites
        # across ALL intermediate GitHub command commits before any stage.
        control_ref = git('rev-parse', REQUEST_REF).decode().strip()
        validate_control_ref_history(STATE, control_ref)
        latest = json_read(show(RECEIPT_REF, LATEST_PATH))
        # Look up the exact immutable preceding stage rather than assuming
        # that every more recent receipt is the same prior success.
        prev = (
            json_read(show(RECEIPT_REF, f'receipts/{cmd["previous_request_id"]}.json'))
            if cmd['previous_request_id'] else None
        )
        if seen.exists():
            already = json_read(show(RECEIPT_REF, f'receipts/{req}.json'))
            if already is not None:
                return 0
            # A prior service was interrupted after starting. Do not retry
            # an operation that could already have changed the live servers.
            unknown = {
                **cmd, 'status': 'unknown', 'exit_code': None,
                'started_at_utc': utcnow(), 'finished_at_utc': utcnow(),
                'failure_category': 'InterruptedStageUnknown',
                'markers': [], 'failed_tests': [], 'test_counts': [],
            }
            atomic_json(pending, unknown)
            publish_receipt(unknown)
            pending.unlink()
            return 0
        try:
            validate_chain(cmd, prev, latest)
        except GateError as exc:
            receipt = {
                **cmd, 'status': 'blocked', 'exit_code': 1,
                'started_at_utc': utcnow(), 'finished_at_utc': utcnow(),
                'failure_category': 'StageChainBlocked', 'markers': [],
                'failed_tests': [], 'test_counts': [],
            }
            # Fail closed on invalid transitions without attempting any execution.
            with (STATE / f'{req}.log').open('w') as log:
                log.write(str(exc) + '\n')
        else:
            receipt = None
        # Mark *before* executing; an interrupted deployment can never be
        # silently retried just because the agent/service restarted.
        fd = os.open(seen, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        if receipt is None:
            receipt = execute(cmd)
        atomic_json(pending, receipt)
        publish_receipt(receipt)
        pending.unlink()
        print(f'RELEASE_AGENT_STAGE={cmd["action"]} RESULT={receipt["status"]}', flush=True)
        return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (GateError, OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print('RELEASE_AGENT_ERROR=' + type(exc).__name__, file=sys.stderr)
        raise SystemExit(1)
