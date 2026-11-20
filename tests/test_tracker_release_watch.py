"""Offline integration tests for the GitHub-managed Tracker release watcher.

Runs the real Bash watcher against disposable bare Git remotes and stubbed
systemd/journal programs. It never touches live DEV or PROD.
"""
import json
import os
from pathlib import Path
import subprocess
import textwrap

import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'scripts' / 'tracker-release-watch.sh'
BASE = '5e78dfcdc8d9612266aa2aca26755957bad02561'
TARGET = '7c662491c3a233b3df60842bbaeaa2dfbc995f06'
REQUEST = {
    'schema': 1, 'request_id': 'r711-925bf13e6d74',
    'action': 'dev_install', 'release': 711,
    'target': TARGET, 'base': BASE,
    'ref': 'release/711-blend-dose-corrections',
    'previous_request_id': 'r711-3b7f6c20ad8e',
}


def git(repo, *args):
    r = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    assert r.returncode == 0, (args, r.stderr)
    return r.stdout.strip()


def write_json(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2) + '\n')


def receipt_for(request, **changes):
    r = {**request, 'status': 'passed', 'exit_code': 0,
         'markers': [f"RELEASE_{request['release']}_DEV_INSTALL=SUCCESS"],
         'test_counts': ['68 passed, 1 warning'], 'failed_tests': []}
    r.update(changes)
    return r


@pytest.fixture()
def env(tmp_path):
    remote = tmp_path / 'remote.git'
    app = tmp_path / 'app'
    other = tmp_path / 'event-writer'
    logs = tmp_path / 'logs'
    stubs = tmp_path / 'stubs'
    stubs.mkdir()
    logs.mkdir()
    subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
    subprocess.run(['git', 'clone', str(remote), str(app)], check=True, capture_output=True)
    git(app, 'config', 'user.name', 'Test')
    git(app, 'config', 'user.email', 'test@example.com')
    (app / 'README').write_text('installed app untouched\n')
    git(app, 'add', 'README')
    git(app, 'commit', '-m', 'initial')
    git(app, 'branch', '-M', 'main')
    git(app, 'push', 'origin', 'main')
    git(app, 'checkout', '-b', 'tracker-release-requests')
    write_json(app / 'control/current.json', REQUEST)
    git(app, 'add', '.')
    git(app, 'commit', '-m', 'request')
    git(app, 'push', 'origin', 'tracker-release-requests')
    git(app, 'checkout', 'main')
    # second checkout only writes synthetic receipt events
    subprocess.run(['git', 'clone', '-b', 'main', str(remote), str(other)], check=True, capture_output=True)
    git(other, 'config', 'user.name', 'Test')
    git(other, 'config', 'user.email', 'test@example.com')
    (stubs / 'hostname').write_text('#!/bin/sh\necho tracker-dev\n')
    (stubs / 'systemctl').write_text('''#!/bin/bash
case "$1" in
  start)
    echo start >> "$MOCK_CALLS"
    if [[ -n "${MOCK_HOOK:-}" ]]; then bash "$MOCK_HOOK"; fi
    ;;
  show) echo inactive ;;
  *) echo "unexpected: $*" >&2; exit 13 ;;
esac
''')
    (stubs / 'journalctl').write_text('#!/bin/sh\necho journal-notes\n')
    for file in stubs.iterdir():
        file.chmod(0o755)
    watcher = tmp_path / 'watcher.sh'
    contents = SOURCE.read_text()
    assert contents.count("readonly APP='/opt/tracker'") == 1
    assert contents.count("readonly LOGDIR='/var/log/tracker-release-agent'") == 1
    contents = contents.replace("readonly APP='/opt/tracker'", f"readonly APP='{app}'")
    contents = contents.replace("readonly LOGDIR='/var/log/tracker-release-agent'", f"readonly LOGDIR='{logs}'")
    contents = contents.replace('"$LOGDIR" == \'/var/log/tracker-release-agent\'', f'"$LOGDIR" == \'{logs}\'')
    contents = contents.replace('[[ -d "$APP/.git" ]]', '[[ -e "$APP/.git" ]]')
    watcher.write_text(contents)
    calls = tmp_path / 'calls'
    environ = dict(os.environ, PATH=str(stubs) + ':' + os.environ['PATH'], MOCK_CALLS=str(calls))
    return {'app': app, 'other': other, 'logs': logs, 'calls': calls, 'watcher': watcher, 'env': environ, 'remote': remote}


def run(env, timeout=35):
    return subprocess.run(['bash', str(env['watcher'])], capture_output=True, text=True,
                          env=env['env'], timeout=timeout)


def push_receipt(env, value):
    other = env['other']
    git(other, 'checkout', '-B', 'tracker-release-receipts', 'main')
    request_id = value['request_id']
    write_json(other / 'receipts/latest.json', value)
    write_json(other / f'receipts/{request_id}.json', value)
    git(other, 'add', 'receipts')
    git(other, 'commit', '-m', 'receipt')
    git(other, 'push', 'origin', 'tracker-release-receipts')
    git(other, 'checkout', 'main')


def test_source_is_syntax_valid():
    subprocess.run(['bash', '-n', str(SOURCE)], check=True)


def test_preexisting_passed_receipt_no_systemctl_invocation(env):
    push_receipt(env, receipt_for(REQUEST))
    r = run(env)
    assert r.returncode == 0, r.stderr + r.stdout
    assert 'Status: passed' in r.stdout
    assert 'No service restart needed' in r.stdout
    assert not env['calls'].exists()
    assert git(env['app'], 'status', '--porcelain') == ''


def test_preexisting_failed_receipt_returns_nonzero_no_restart(env):
    push_receipt(env, receipt_for(REQUEST, status='failed', exit_code=1, failure_category='TestAssertion'))
    r = run(env)
    assert r.returncode == 2, r.stderr + r.stdout
    assert 'Status: failed' in r.stdout
    assert not env['calls'].exists()


@pytest.mark.parametrize('updates', [
    {'request_id': ''}, {'request_id': 'bad/name'}, {'action': ''},
    {'target': 'bad'}, {'release': '711'}, {'schema': None},
    {'ref': 'release/710-wrong-number'},
])
def test_malformed_queue_fails_before_agent_start(env, updates):
    request = {**REQUEST, **updates}
    app = env['app']
    git(app, 'checkout', 'tracker-release-requests')
    write_json(app / 'control/current.json', request)
    git(app, 'add', '.')
    git(app, 'commit', '-m', 'bad request')
    git(app, 'push', 'origin', 'tracker-release-requests')
    git(app, 'checkout', 'main')
    r = run(env)
    assert r.returncode != 0
    assert 'agent NOT started' in r.stderr or 'Refusing to trigger' in r.stderr
    assert not env['calls'].exists()


def test_prod_command_refused_without_systemctl(env):
    app=env['app']
    git(app, 'checkout', 'tracker-release-requests')
    write_json(app / 'control/current.json', {**REQUEST, 'action':'prod_deploy'})
    git(app, 'add', '.')
    git(app, 'commit', '-m', 'prod action')
    git(app, 'push', 'origin', 'tracker-release-requests')
    git(app, 'checkout', 'main')
    r=run(env)
    assert r.returncode != 0
    assert 'does not start PROD stages' in r.stderr
    assert not env['calls'].exists()


def test_triggers_queued_stage_and_follows_its_log(env):
    hook = env['watcher'].parent / 'hook.sh'
    req=REQUEST['request_id']
    # Service stub simulates the completed run, local log and published receipt.
    json_payload=json.dumps(receipt_for(REQUEST))
    hook.write_text(textwrap.dedent(f'''\
        #!/bin/bash
        set -e
        printf 'SIMULATED_SCOPED_TEST=PASSED\\n' > {str(env['logs'] / (req + '.log'))!r}
        git -C {str(env['other'])!r} checkout -B tracker-release-receipts main >/dev/null
        mkdir -p {str(env['other'] / 'receipts')!r}
        printf '%s\\n' {json_payload!r} > {str(env['other'] / 'receipts/latest.json')!r}
        cp {str(env['other'] / 'receipts/latest.json')!r} {str(env['other'] / ('receipts/' + req + '.json'))!r}
        git -C {str(env['other'])!r} add receipts
        git -C {str(env['other'])!r} commit -m receipt >/dev/null
        git -C {str(env['other'])!r} push origin tracker-release-receipts >/dev/null
        git -C {str(env['other'])!r} checkout main >/dev/null
    '''))
    env['env']['MOCK_HOOK'] = str(hook)
    r = run(env)
    assert r.returncode == 0, r.stderr + r.stdout
    assert env['calls'].read_text().strip() == 'start'
    assert 'SIMULATED_SCOPED_TEST=PASSED' in r.stdout
    assert 'Status: passed' in r.stdout
    assert git(env['app'], 'status', '--porcelain') == ''
