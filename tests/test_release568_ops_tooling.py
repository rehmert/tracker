"""Release 568: offline safety contracts for DEV-controlled deployments.

No network, production host, signing key, systemd unit, or database is used.
"""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "scripts/tracker_promote568.py"
PROD = ROOT / "scripts/tracker_prod_remote568.sh"
READINESS = ROOT / "scripts/tracker_readiness568.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_remote_executor_has_valid_shell_syntax():
    result = subprocess.run(
        ["bash", "-n", str(PROD)],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_host_controller_help_and_invalid_input_are_safe():
    help_result = subprocess.run(
        [sys.executable, str(DEV), "--help"],
        text=True, capture_output=True, check=False,
    )
    assert help_result.returncode == 0
    assert "--execute" in help_result.stdout
    for args in (
        [],
        ["--release", "568", "--target", "bad", "--prod-base", "bad",
         "--ref", "release/568-tooling", "--execute"],
    ):
        result = subprocess.run(
            [sys.executable, str(DEV), *args],
            text=True, capture_output=True, check=False,
        )
        assert result.returncode != 0
        assert "PROMOTED_COMMIT=" not in result.stdout
        assert "PROD_INSTALLED_COMMIT=" not in result.stdout


def test_release_arguments_require_exact_ancestry_identifiers():
    tool = load(DEV, "dev_control568")
    tool.validate(568, "b" * 40, "a" * 40, "release/568-safety")
    invalid = (
        (568, "b" * 39, "a" * 40, "release/568-safety"),
        (568, "B" * 40, "a" * 40, "release/568-safety"),
        (568, "a" * 40, "a" * 40, "release/568-safety"),
        (568, "b" * 40, "a" * 40, "release/567-old"),
        (568, "b" * 40, "a" * 40, "release/568-../unsafe"),
        (568, "b" * 40, "a" * 40, "main"),
    )
    for args in invalid:
        with pytest.raises(tool.ReleaseError):
            tool.validate(*args)


def test_signed_qualification_marker_tolerates_indented_heading_only():
    tool = load(DEV, "dev_control568_qual")
    target = "c" * 40
    required = [
        *tool.QUALIFICATION,
        " TRACKER RELEASE DEPLOYMENT SUCCESS",
        "EXIT_STATUS=0",
        f"DEV_QUALIFIED_COMMIT={target}",
    ]
    tool.verified_log("\n".join(required) + "\n", target)

    for missing in required:
        lines = [line for line in required if line != missing]
        with pytest.raises(tool.ReleaseError):
            tool.verified_log("\n".join(lines), target)

    with pytest.raises(tool.ReleaseError):
        tool.verified_log("\n".join(required + ["EXIT_STATUS=2"]), target)


def test_remote_runner_keeps_prod_approval_and_rollback_guards():
    source = PROD.read_text(encoding="utf-8")
    controller = DEV.read_text(encoding="utf-8")
    for marker in (
        '$(hostname -s)',
        'tracker-prod',
        'tracker-verify-dev-approval',
        'git merge-base --is-ancestor "$BASE" "$TARGET"',
        'bash "$RUNNER"',
        '--instance PROD',
        '--ref main',
        'TRACKER RELEASE DEPLOYMENT SUCCESS',
        'EXIT_STATUS=0',
        'PROD_DEPLOY_VERIFIED=',
        'REMOTE_DEPLOY_EXIT_STATUS=',
    ):
        assert marker in source
    for marker in (
        '"--execute"',
        '"tracker-dev"',
        '"BatchMode=yes"',
        '"StrictHostKeyChecking=yes"',
        'sign_and_transfer(args.target)',
        'promote(args.target, args.prod_base)',
        'deploy(args.release, args.target, args.prod_base)',
        'verified_log(',
        'PROMOTED_BUT_PROD_NOT_VERIFIED',
    ):
        assert marker in controller
    assert controller.index("sign_and_transfer(args.target)") < (
        controller.index("promote(args.target, args.prod_base)")
    ) < controller.index("deploy(args.release, args.target, args.prod_base)")



def test_prod_runner_is_exact_signed_target_blob_not_installed_launcher():
    source = PROD.read_text(encoding="utf-8")
    assert 'bash scripts/tracker-release.sh' not in source
    assert 'git rev-parse "$TARGET:scripts/tracker-release.sh"' in source
    assert 'git show "$TARGET:scripts/tracker-release.sh" > "$RUNNER"' in source
    assert 'git hash-object "$RUNNER"' in source
    assert '"$EXPECTED_RUNNER"' in source
    assert 'bash -n "$RUNNER"' in source
    assert 'STAGE="$(mktemp -d /tmp/tracker-prod-runner.XXXXXXXX)"' in source
    assert 'chmod 700 "$STAGE"' in source
    assert 'PROD_PINNED_RUNNER_BLOB=' in source
    # All content and syntax checks must precede the deployment log reset
    # and exact-target runner execution, so failure cannot trigger a deploy.
    assert source.index('git show "$TARGET:scripts/tracker-release.sh"') < (
        source.index('git hash-object "$RUNNER"')
    ) < source.index('bash -n "$RUNNER"') < (
        source.index(': > "$LOG"')
    ) < source.index('bash "$RUNNER"')
    # Keep all existing production gates and cleanup evidence intact.
    assert source.index('tracker-verify-dev-approval "$TARGET"') < (
        source.index('git show "$TARGET:scripts/tracker-release.sh"')
    )
    assert 'REMOTE_DEPLOY_EXIT_STATUS=$rc' in source
    assert 'rmdir -- "$STAGE"' in source


def test_readiness_report_is_safe_and_has_no_install_side_effects(tmp_path):
    tool = load(READINESS, "readiness568")
    (tmp_path / "requirements.txt").write_text(
        "fastapi>=0.115\nsqlalchemy==2.0.0\n", encoding="utf-8"
    )
    (tmp_path / "requirements-dev.txt").write_text(
        "-r requirements.txt\npytest>=8\n", encoding="utf-8"
    )
    specs = tool.requirement_specs(tmp_path)
    assert [item["exact_pin"] for item in specs["requirements.txt"]] == [
        False, True,
    ]
    assert len(specs["requirements-dev.txt"]) == 1
    assert "fastapi" in tool.package_versions(("fastapi",))
    source = READINESS.read_text(encoding="utf-8")
    assert "importlib.metadata" in source
    assert "tracker-security-audit536.py" in source
    assert "pip install" not in source
    assert "os.environ" not in source
    cli = subprocess.run(
        [sys.executable, str(READINESS), "--instance", "DEV", "--json"],
        text=True, capture_output=True, check=False,
    )
    assert cli.returncode == 0, cli.stderr
    assert '"instance": "DEV"' in cli.stdout
    assert '"packages"' in cli.stdout

def test_default_mode_does_not_sign_push_or_deploy(monkeypatch, capsys):
    tool = load(DEV, "dev_control568_dry_run")
    invoked = []

    def no_ops(*args):
        invoked.append(args)

    monkeypatch.setattr(tool, "preflight", no_ops)
    monkeypatch.setattr(tool, "sign_and_transfer", lambda *_: pytest.fail("signed"))
    monkeypatch.setattr(tool, "promote", lambda *_: pytest.fail("pushed"))
    monkeypatch.setattr(tool, "deploy", lambda *_: pytest.fail("deployed"))
    args = [
        "--release", "568", "--target", "b" * 40,
        "--prod-base", "a" * 40, "--ref", "release/568-safe",
    ]
    assert tool.main(args) == 0
    assert len(invoked) == 1
    assert "DRY_RUN=PASSED" in capsys.readouterr().out


def test_execute_stops_before_push_if_signature_transfer_fails(monkeypatch):
    tool = load(DEV, "dev_control568_fail_closed")
    monkeypatch.setattr(tool, "preflight", lambda *_: None)

    def reject(*_):
        raise tool.ReleaseError("PROD signature rejected")

    monkeypatch.setattr(tool, "sign_and_transfer", reject)
    monkeypatch.setattr(tool, "promote", lambda *_: pytest.fail("pushed"))
    monkeypatch.setattr(tool, "deploy", lambda *_: pytest.fail("deployed"))
    args = [
        "--release", "568", "--target", "b" * 40,
        "--prod-base", "a" * 40, "--ref", "release/568-safe",
        "--execute",
    ]
    assert tool.main(args) == 1


def test_execute_invokes_signed_promotion_before_remote_deploy(monkeypatch):
    tool = load(DEV, "dev_control568_order")
    phases = []
    monkeypatch.setattr(tool, "preflight", lambda *_: phases.append("preflight"))
    monkeypatch.setattr(tool, "sign_and_transfer", lambda *_: phases.append("sign"))
    monkeypatch.setattr(tool, "promote", lambda *_: phases.append("promote"))
    monkeypatch.setattr(tool, "deploy", lambda *_: phases.append("deploy"))
    args = [
        "--release", "568", "--target", "b" * 40,
        "--prod-base", "a" * 40, "--ref", "release/568-safe",
        "--execute",
    ]
    assert tool.main(args) == 0
    assert phases == ["preflight", "sign", "promote", "deploy"]
