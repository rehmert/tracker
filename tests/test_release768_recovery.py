"""Release 768: exact failed-767 recovery and relative live data path tests.

No real PROD data, network or release stage is invoked by these tests.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load(path, name):
    spec = spec_from_file_location(name, SCRIPTS / path)
    assert spec is not None and spec.loader is not None
    obj = module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


guard = load("tracker-prod-schema-backup767.py", "recovery768_guard")
agent = load("tracker-release-agent745.py", "recovery768_controller")
promoter = load("tracker_promote568.py", "recovery768_promoter")

OLD = "5d23aaf4f7e7fa4b54c1d5535a622bdd9e9aac13"
PROD = "8c67580611fd945d9ae83f8015f071a24ab6fee5"
NEW_REF = "release/768-prod-relative-data-path-recovery"


def fixture_env(tmp_path, value):
    root = tmp_path / "tracker"
    root.mkdir()
    database = root / "data"
    database.mkdir()
    (database / "tracker.db").write_bytes(b"synthetic; real database not needed")
    env = tmp_path / "tracker.env"
    env.write_text(f"TRACKER_DATA_DIR={value}\n")
    return root, env, database


@pytest.mark.parametrize("value", ["data", "./data", "'data'", '"data"'])
def test_768_relative_config_matches_tracker_working_directory(tmp_path, value):
    root, env, expected = fixture_env(tmp_path, value)
    assert guard.resolve_data_dir768(root, env) == expected.resolve()


def test_768_absolute_config_and_default(tmp_path):
    root, env, expected = fixture_env(tmp_path, "data")
    env.write_text("TRACKER_DATA_DIR=" + str(expected) + "\n")
    assert guard.resolve_data_dir768(root, env) == expected
    env.write_text("TRACKER_CURRENCY=$\n")
    assert guard.resolve_data_dir768(root, env) == expected


def test_768_symlink_and_missing_db_rejected(tmp_path):
    root, env, expected = fixture_env(tmp_path, "data")
    linked = root / "linked"
    linked.symlink_to(expected, target_is_directory=True)
    env.write_text("TRACKER_DATA_DIR=linked\n")
    with pytest.raises(ValueError):
        guard.resolve_data_dir768(root, env)
    env.write_text("TRACKER_DATA_DIR=missing\n")
    with pytest.raises(ValueError):
        guard.resolve_data_dir768(root, env)
    env.write_text("TRACKER_DATA_DIR=data\n")
    (expected / "tracker.db").unlink()
    (expected / "tracker.db").symlink_to(root / "other.db")
    (root / "other.db").write_bytes(b"synthetic")
    with pytest.raises(ValueError):
        guard.resolve_data_dir768(root, env)


def prior_command():
    return {
        "schema": 1, "request_id": "r767-deploy5d23aaf4",
        "action": "prod_deploy", "release": 767,
        "target": OLD, "base": PROD,
        "ref": "release/767-prod-device-schema-guard",
        "previous_request_id": "r767-preflight5d23aa",
    }


def recovery_command():
    return {
        "schema": 1, "request_id": "r768-aaaaaaaabbbb",
        "action": "qualify", "release": 768,
        "target": "a" * 40, "base": OLD, "ref": NEW_REF,
        "previous_request_id": None,
    }


def failed_receipt():
    return {
        **prior_command(), "status": "failed", "exit_code": 1,
        "failure_category": "PromotionOrDeploymentGate",
        "markers": [
            "PREFLIGHT=PASSED", "PROMOTED_COMMIT=" + OLD,
            "REMOTE_DEPLOY_EXIT_STATUS=1",
        ],
    }


def test_768_only_the_exact_failed_prod_receipt_allows_new_qualification():
    agent.validate_control_transition(
        prior_command(), recovery_command(), failed_receipt()
    )
    for modify in (
        {"status": "unknown"},
        {"failure_category": "TestAssertion"},
        {"markers": []},
        {"exit_code": 0},
        {"target": PROD},
    ):
        receipt = {**failed_receipt(), **modify}
        with pytest.raises(agent.GateError):
            agent.validate_control_transition(
                prior_command(), recovery_command(), receipt
            )
    for modify in (
        {"action": "prod_deploy"},
        {"base": PROD},
        {"release": 769},
        {"previous_request_id": prior_command()["request_id"]},
        {"ref": "release/768-other"},
        {"target": OLD},
    ):
        cmd = {**recovery_command(), **modify}
        with pytest.raises(agent.GateError):
            agent.validate_control_transition(
                prior_command(), cmd, failed_receipt()
            )


def test_768_controller_continues_to_forbid_generic_failed_deploys():
    old = {**prior_command(), "release": 766,
           "ref": "release/766-other", "request_id": "r766-1234567890ab"}
    receipt = {**old, "status": "failed", "exit_code": 1,
               "failure_category": "PromotionOrDeploymentGate",
               "markers": ["REMOTE_DEPLOY_EXIT_STATUS=1"]}
    with pytest.raises(agent.GateError):
        agent.validate_control_transition(old, recovery_command(), receipt)


def test_768_promoter_retains_705_no_environment_path_contract():
    source = (SCRIPTS / "tracker_promote568.py").read_text()
    assert '"/etc/tracker.env"' not in source
    assert '"if not path.is_absolute():" not in source' in source
    assert '"path = root / path" not in source' in source


def test_768_promoter_requires_exact_existing_main_and_prod_base():
    target = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                     cwd=ROOT, text=True).strip()
    # Exercise the real one-off source-scope and ancestry checks.
    assert promoter.recovery_768_main_allowed(OLD, target, PROD)
    assert not promoter.recovery_768_main_allowed(PROD, target, PROD)
    assert not promoter.recovery_768_main_allowed(OLD, target, OLD)
    assert not promoter.recovery_768_main_allowed(OLD, OLD, PROD)


def test_768_app_source_did_not_change_since_dev_766():
    target = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                     cwd=ROOT, text=True).strip()
    guard.review_source(ROOT, PROD, target)
    diff = subprocess.check_output(
        ["git", "diff", "--name-only", OLD, target],
        cwd=ROOT, text=True,
    ).splitlines()
    assert diff and all(p.startswith(("scripts/","tests/","docs/")) for p in diff)


def test_768_controller_derives_from_signed_ops_without_losing_dev_recovery():
    op_commit = "76f7679534ad3d430bf21381cc0d542761bc31d7"
    ops = subprocess.check_output([
        "git", "show", f"{op_commit}:scripts/tracker-release-agent.py"
    ], cwd=ROOT, text=True)
    target = (SCRIPTS/"tracker-release-agent745.py").read_text()
    assert "if status == 'failed' and previous['action'] == 'dev_install':" in target
    assert "clean_main(previous['base'])" in target
    marker = "    # Exact recovery of a failed PROD deployment whose *source* was promoted"
    assert target.count(marker) == 1
    start = target.index(marker)
    finish = target.index(
        "    if status == 'failed' and previous['action'] == 'qualify':", start
    )
    assert target[:start] + target[finish:] == ops


def test_768_bootstrap_checks_signed_ops_host_fingerprint():
    src = (SCRIPTS/"tracker-recovery-bootstrap768.sh").read_text()
    assert 'TRUSTED_OPS=76f7679534ad3d430bf21381cc0d542761bc31d7' in src
    assert 'TRUSTED_BLOB="$(git rev-parse "$TRUSTED_OPS:scripts/tracker-release-agent.py")"' in src
    assert '"$HOST_BLOB" == "$TRUSTED_BLOB"' in src
    assert 'RELEASE_768_TRUSTED_HOST_CONTROLLER=OPS_PINNED_VERIFIED' in src
    assert 'agent-before768.py' in src


def test_768_all_privileged_release_shell_scripts_parse():
    scripts = (
        "tracker-qualify768.sh",
        "tracker-install768.sh",
        "tracker-release-scoped768.sh",
        "tracker-recovery-bootstrap768.sh",
        "tracker_prod_remote568.sh",
    )
    for filename in scripts:
        result = subprocess.run(
            ["bash", "-n", str(SCRIPTS / filename)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (filename, result.stderr)
        content = (SCRIPTS / filename).read_text()
        assert "==\n" not in content, filename


def test_768_bootstrap_is_valid_bash_before_any_privileged_action():
    bootstrap = SCRIPTS / "tracker-recovery-bootstrap768.sh"
    syntax = subprocess.run(
        ["bash", "-n", str(bootstrap)], capture_output=True, text=True
    )
    assert syntax.returncode == 0, syntax.stderr
    # A comparison must not break immediately after '==' inside [[ ]].
    assert "==\n" not in bootstrap.read_text()


def test_768_bootstrap_changes_only_host_agent_after_isolated_checks():
    src = (SCRIPTS/"tracker-recovery-bootstrap768.sh").read_text()
    assert "RELEASE_768_CONTROLLER_RECOVERY_BOOTSTRAP=SUCCESS" in src
    assert "r767-deploy5d23aaf4" in src
    assert "git worktree add --detach" in src
    assert "git hash-object" in src
    assert "flock -n 9" in src
    assert "systemctl is-active --quiet tracker" in src
    assert "mv -f" in src
    assert "PROD" in src
    assert "update-index" not in src
    assert "git push" not in src
    assert "tracker-release-agent.service" in src
    assert "RELEASE_768_FAILED_RECEIPT=IMMUTABLY_VERIFIED" in src
    assert "RELEASE_768_PROD_STILL_765=VERIFIED" in src


def test_768_remote_guard_accepts_only_the_two_reviewed_versions():
    src = (SCRIPTS/"tracker_prod_remote568.sh").read_text()
    assert 'if [[ "$RELEASE" == 767 || "$RELEASE" == 768 ]]; then' in src
    assert 'RELEASE_767_PROD_SCHEMA_BACKUP=PASSED' in src
    assert 'bash "$RUNNER"' in src
    assert 'REMOTE_DEPLOY_EXIT_STATUS=$rc' in src
