"""Offline invariants for the DEV-owned 'proceed' release agent."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/tracker-release-agent.py'
spec = importlib.util.spec_from_file_location('tracker_release_agent', SOURCE)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)

BASE = '5e78dfcdc8d9612266aa2aca26755957bad02561'
TARGET = '573ce28e9301b2d0e67abd0b936ca2a51d628ad5'


def cmd(action='qualify', previous=None, request_id='r711-123456789abc'):
    return {
        'schema': 1, 'request_id': request_id, 'action': action,
        'release': 711, 'target': TARGET, 'base': BASE,
        'ref': 'release/711-blend-dose-corrections',
        'previous_request_id': previous,
    }


def receipt(action, request_id, *, status='passed'):
    return {**cmd(action=action, request_id=request_id), 'status': status}


def test_711_qualify_allows_no_previous_stage():
    request = agent.validate_command(cmd())
    agent.validate_chain(request, None)


@pytest.mark.parametrize('bad', [
    {'action': 'deploy'},
    {'release': 710},
    {'target': 'deadbeef'},
    {'base': TARGET},
    {'ref': '../main'},
    {'request_id': 'abc; rm -rf /'},
    {'extra': 'unexpected'},
    {'previous_request_id': 'r711-abcdef012345'},
])
def test_711_rejects_malformed_or_extra_request_fields(bad):
    body = cmd()
    body.update(bad)
    with pytest.raises(agent.GateError):
        agent.validate_command(body)


@pytest.mark.parametrize('action, prior', [
    ('dev_install', 'qualify'),
    ('prod_preflight', 'dev_install'),
    ('prod_deploy', 'prod_preflight'),
])
def test_711_each_stage_requires_exact_previous_pass(action, prior):
    previous_id = 'r711-abcdef012345'
    request = agent.validate_command(cmd(action, previous_id))
    agent.validate_chain(request, receipt(prior, previous_id))
    with pytest.raises(agent.GateError):
        agent.validate_chain(request, receipt(prior, previous_id, status='failed'))
    with pytest.raises(agent.GateError):
        agent.validate_chain(request, receipt(prior, 'r711-555555555555'))
    with pytest.raises(agent.GateError):
        agent.validate_chain(request, receipt('qualify' if prior != 'qualify' else 'dev_install', previous_id))
    with pytest.raises(agent.GateError):
        agent.validate_chain(request, {**receipt(prior, previous_id), 'target': BASE})


def test_721_catchup_prod_base_can_differ_only_at_preflight():
    """DEV 720 -> 721 while PROD 715 -> 721 is a valid signed catch-up."""
    dev_base = BASE
    installed_prod_base = 'ab70236618df66b8a959c765abf38dbcd59b29d7'
    prior_id = 'r711-abcdef012345'
    dev_receipt = receipt('dev_install', prior_id)
    assert dev_receipt['base'] == dev_base

    preflight = cmd('prod_preflight', prior_id, 'r711-111111111111')
    preflight['base'] = installed_prod_base
    request = agent.validate_command(preflight)
    agent.validate_chain(request, dev_receipt)

    # The next PROD stage must keep the actual PROD base from preflight.
    deploy = cmd('prod_deploy', preflight['request_id'], 'r711-222222222222')
    deploy['base'] = installed_prod_base
    agent.validate_chain(
        agent.validate_command(deploy),
        {**preflight, 'status': 'passed', 'request_id': preflight['request_id']},
    )
    deploy['base'] = dev_base
    with pytest.raises(agent.GateError):
        agent.validate_chain(
            agent.validate_command(deploy),
            {**preflight, 'status': 'passed'},
        )


@pytest.mark.parametrize('field,value', [
    ('target', BASE), ('ref', 'release/711-other-slug'),
    ('release', 710), ('request_id', 'r711-555555555555'),
])
def test_721_catchup_still_requires_matching_dev_receipt(field, value):
    previous_id = 'r711-abcdef012345'
    request = cmd('prod_preflight', previous_id, 'r711-111111111111')
    request['base'] = 'ab70236618df66b8a959c765abf38dbcd59b29d7'
    prior = receipt('dev_install', previous_id)
    prior[field] = value
    with pytest.raises(agent.GateError):
        agent.validate_chain(agent.validate_command(request), prior)


def test_721_catchup_rejects_unpassed_or_wrong_previous_stage():
    previous_id = 'r711-abcdef012345'
    request = cmd('prod_preflight', previous_id, 'r711-111111111111')
    request['base'] = 'ab70236618df66b8a959c765abf38dbcd59b29d7'
    for old in (
        receipt('dev_install', previous_id, status='failed'),
        receipt('qualify', previous_id),
        receipt('dev_install', 'r711-555555555555'),
    ):
        with pytest.raises(agent.GateError):
            agent.validate_chain(agent.validate_command(request), old)


def test_721_recover_only_same_never_executed_chain_block():
    previous_id = 'r711-abcdef012345'
    request = cmd('prod_preflight', previous_id, 'r711-222222222222')
    request['base'] = 'ab70236618df66b8a959c765abf38dbcd59b29d7'
    approved = receipt('dev_install', previous_id)
    blocked = {
        **request, 'request_id': 'r711-111111111111', 'status': 'blocked',
        'failure_category': 'StageChainBlocked', 'exit_code': 1,
    }
    agent.validate_chain(agent.validate_command(request), approved, blocked)
    agent.validate_chain(agent.validate_command(request), approved, approved)

    for wrong in (
        {**blocked, 'status': 'unknown'},
        {**blocked, 'status': 'failed'},
        {**blocked, 'failure_category': 'PromotionOrDeploymentGate'},
        {**blocked, 'action': 'prod_deploy'},
        {**blocked, 'target': BASE},
        {**blocked, 'base': BASE},
        {**blocked, 'ref': 'release/711-other-slug'},
        {**blocked, 'previous_request_id': 'r711-333333333333'},
    ):
        with pytest.raises(agent.GateError):
            agent.validate_chain(agent.validate_command(request), approved, wrong)


def test_721_immutable_previous_stage_must_pass_even_after_blocked_attempt():
    previous_id = 'r711-abcdef012345'
    request = cmd('prod_preflight', previous_id, 'r711-222222222222')
    request['base'] = 'ab70236618df66b8a959c765abf38dbcd59b29d7'
    blocked = {
        **request, 'request_id': 'r711-111111111111', 'status': 'blocked',
        'failure_category': 'StageChainBlocked',
    }
    for invalid in (None, receipt('dev_install', previous_id, status='failed'),
                    receipt('qualify', previous_id)):
        with pytest.raises(agent.GateError):
            agent.validate_chain(agent.validate_command(request), invalid, blocked)


def test_711_qualification_success_requires_both_completion_markers():
    data = '''RELEASE_711_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY
RELEASE_711_EXIT_STATUS=0
'''
    agent.validate_success(cmd(), data)
    with pytest.raises(agent.GateError):
        agent.validate_success(cmd(), 'RELEASE_711_EXIT_STATUS=0\n')


def test_711_receipt_strips_raw_messages_and_sensitive_values():
    message = '''FAILED tests/test_release711.py::test_private[patient-social-security-999]
RELEASE_604_IMPACT_PREFLIGHT=FAILED
RELEASE_SECRET_KEY=private-secret
RELEASE_711_EXIT_STATUS=1
E     999-12-3456
7 passed, 1 failed in 5.00s
'''
    safe = agent.safe_diagnostics(message)
    serialized = json.dumps(safe)
    assert '999-12-3456' not in serialized
    assert 'private-secret' not in serialized
    assert 'patient' not in serialized
    assert safe['failed_tests'] == ['tests/test_release711.py']
    assert safe['markers'] == ['RELEASE_604_IMPACT_PREFLIGHT=FAILED', 'RELEASE_711_EXIT_STATUS=1']
    assert agent.failure_kind(message) == 'AssetImpactPreflight'


def _git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


def test_711_publishes_receipt_without_touching_installed_checkout():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        origin = root / 'remote.git'
        repo = root / 'installed'
        state = root / 'state'
        state.mkdir(mode=0o700)
        subprocess.run(['git', 'init', '--bare', str(origin)], check=True, capture_output=True)
        subprocess.run(['git', 'clone', str(origin), str(repo)], check=True, capture_output=True)
        _git(repo, 'config', 'user.name', 'Test')
        _git(repo, 'config', 'user.email', 'test@example.com')
        (repo / 'README.md').write_text('installed source\n')
        _git(repo, 'add', 'README.md')
        _git(repo, 'commit', '-m', 'initial')
        _git(repo, 'branch', '-M', 'main')
        _git(repo, 'push', 'origin', 'main')
        _git(repo, 'push', 'origin', 'HEAD:refs/heads/tracker-release-receipts')
        original = _git(repo, 'rev-parse', 'HEAD')
        with patch.object(agent, 'APP', repo), patch.object(agent, 'STATE', state):
            record = {**cmd(), 'status': 'passed', 'exit_code': 0,
                      'markers': ['RELEASE_711_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY']}
            agent.publish_receipt(record)
            agent.publish_receipt(record)
            assert agent.json_read(agent.show(agent.RECEIPT_REF, 'receipts/latest.json')) == record
            assert agent.json_read(agent.show(agent.RECEIPT_REF, f'receipts/{record["request_id"]}.json')) == record
        assert _git(repo, 'rev-parse', 'HEAD') == original
        assert not _git(repo, 'status', '--porcelain')
