"""Release 577: DEV qualification receipt is fail-closed and auditable."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tracker_dev_log577.py"
RUNNER = ROOT / "scripts/tracker-release.sh"


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("tracker_dev_log577", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evidence(tool, target="a" * 40):
    return "\n".join([
        "Started: 2026-11-12T04:00:00+00:00; instance: DEV",
        f"CANDIDATE_COMMIT={target}",
        *tool.REQUIRED,
        " TRACKER RELEASE DEPLOYMENT SUCCESS",
        "EXIT_STATUS=0",
        "Finished: 2026-11-12T04:04:00+00:00",
    ]) + "\n"


def test_577_successful_receipt_contains_actual_evidence_and_exact_commit(tool):
    sha = "a" * 40
    result = tool.validated_evidence(evidence(tool), sha)
    assert result.count("DEV_QUALIFIED_COMMIT=") == 1
    assert result.endswith(f"DEV_QUALIFIED_COMMIT={sha}\n")
    for item in tool.REQUIRED:
        assert item in result


@pytest.mark.parametrize("marker", [
    "ISOLATED_BROWSER=PASSED",
    "ISOLATED_STRICT_CSRF_BROWSER=PASSED",
    "=== ALL BACKEND TESTS PASSED ===",
    "=== ISOLATED RESTORE VERIFICATION PASSED ===",
    " TRACKER RELEASE DEPLOYMENT SUCCESS",
    "EXIT_STATUS=0",
    "Finished: 2026-11-12T04:04:00+00:00",
])
def test_577_missing_marker_rejected(tool, marker):
    with pytest.raises(ValueError):
        tool.validated_evidence(evidence(tool).replace(marker, ""), "a" * 40)


def test_577_failed_or_ambiguous_exit_status_rejected(tool):
    for content in (
        evidence(tool).replace("EXIT_STATUS=0", "EXIT_STATUS=1"),
        evidence(tool) + "EXIT_STATUS=1\n",
        evidence(tool) + "EXIT_STATUS=0\n",
        evidence(tool).replace("CANDIDATE_COMMIT=", "OTHER_COMMIT="),
        evidence(tool) + "DEV_QUALIFIED_COMMIT=" + "a" * 40 + "\n",
    ):
        with pytest.raises(ValueError):
            tool.validated_evidence(content, "a" * 40)


def test_577_mismatched_target_rejected(tool):
    with pytest.raises(ValueError):
        tool.validated_evidence(evidence(tool), "b" * 40)
    with pytest.raises(ValueError):
        tool.validated_evidence(evidence(tool), "invalid")


def test_577_workflow_does_not_bypass_guard_or_resume_promotion():
    result = subprocess.run(["bash", "-n", str(RUNNER)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    source = RUNNER.read_text(encoding="utf-8")
    assert 'if ((code==0)) && [[ "$INSTANCE" == DEV ]]' in source
    assert 'code=1' in source
    assert 'tracker_dev_log577.py' in source
    assert source.index("TRACKER RELEASE DEPLOYMENT SUCCESS") < source.index("cleanup()") or (
        # Actual success line is in worker; cleanup is defined earlier.
        source.index("if ! \"$PY\" \"$QA/scripts/tracker_dev_log577.py\"") < source.index("if ((code!=0 && INSTALLED==1))")
    )
    assert "git reset --hard" not in source
    assert "g reset --hard" in source  # Pre-existing guarded rollback retained.
    assert "sign_and_transfer" not in source


def test_577_unsafe_destination_rejected_without_writing(tool, tmp_path, monkeypatch):
    monkeypatch.setattr(tool.os, "geteuid", lambda: 0)
    class Host:
        nodename = "tracker-dev"
    monkeypatch.setattr(tool.os, "uname", lambda: Host())
    with pytest.raises(ValueError, match="Unexpected guarded"):
        tool.preserve(tmp_path / "deployment.log", tmp_path, 577, "a" * 40)
    assert not (tmp_path / "release-577-dev.log").exists()
