"""Release 751: full backend legacy-baseline parity remains fail-closed."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/tracker-backend-parity751.py"
spec = importlib.util.spec_from_file_location("tracker_parity751", SOURCE)
parity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)


def test_751_dev_receipt_accepts_parity_evidence_and_rejects_missing_gates():
    # Exercise the REAL post-install evidence validator, which previously
    # rejected Release 751 because it required an obsolete all-green marker.
    source = ROOT / "scripts/tracker_dev_log577.py"
    spec = importlib.util.spec_from_file_location("tracker_dev_receipt577", source)
    receipt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(receipt)
    target = "a" * 40
    markers = list(receipt.REQUIRED_PARITY_751)
    payload = "\n".join([
        "Started: 2026-11-22T20:00:00+00:00; instance: DEV",
        "CANDIDATE_COMMIT=" + target,
        "QA_FULL_REQUIRED=1",
        *markers,
        "DATABASE_BACKUP=SKIPPED_NO_MIGRATION",
        " TRACKER RELEASE DEPLOYMENT SUCCESS",
        "EXIT_STATUS=0",
        "Finished: 2026-11-22T21:00:00+00:00",
    ]) + "\n"
    result = receipt.validated_evidence(payload, target, release=751)
    assert result.endswith("DEV_QUALIFIED_COMMIT=" + target + "\n")
    assert "=== ALL BACKEND TESTS PASSED ===" not in payload
    # Each expected release-specific marker is independently mandatory.
    for marker in markers:
        with pytest.raises(ValueError, match="Missing DEV qualification evidence"):
            receipt.validated_evidence(
                payload.replace(marker + "\n", ""), target, release=751
            )
    # Older releases cannot substitute parity for their all-green contract.
    with pytest.raises(ValueError, match="Missing DEV qualification evidence"):
        receipt.validated_evidence(payload, target, release=750)
    # The same release cannot validate an unrelated exact commit.
    with pytest.raises(ValueError, match="Missing DEV qualification evidence"):
        receipt.validated_evidence(payload, "b" * 40, release=751)
    with pytest.raises(ValueError, match="successful final exit status"):
        receipt.validated_evidence(
            payload.replace("EXIT_STATUS=0", "EXIT_STATUS=1"),
            target, release=751
        )
    # Old full-suite receipts remain valid for older releases.
    old = payload
    for marker in markers[2:]:
        old = old.replace(marker + "\n", "")
    old += "=== ALL BACKEND TESTS PASSED ===\n"
    assert receipt.validated_evidence(old, target, release=750).endswith(
        "DEV_QUALIFIED_COMMIT=" + target + "\n"
    )


def test_751_chromium_676_parity_merge_retains_all_five_cases():
    required = {nodeid: 'passed' for nodeid in parity.CHROMIUM_676_NODEIDS}
    parallel = {'tests/test_a.py::test_one': 'passed'}
    joined = parity.merge_isolated_chromium676(parallel, required)
    assert joined == parallel | required
    assert len(required) == 5

    # Browser failures, skips, missing cases, duplicates and leaked
    # collection errors are never silently ignored or declared passed.
    for outcome in ('failed', 'error', 'skipped'):
        broken = dict(required)
        broken[next(iter(required))] = outcome
        with pytest.raises(parity.ParityError):
            parity.merge_isolated_chromium676(parallel, broken)
    for nodeid in required:
        with pytest.raises(parity.ParityError, match='coverage mismatch'):
            parity.merge_isolated_chromium676(parallel,
                                              {k: v for k, v in required.items()
                                               if k != nodeid})
    with pytest.raises(parity.ParityError, match='coverage mismatch'):
        parity.merge_isolated_chromium676(parallel,
                                          required | {'tests/test_a.py::test_extra': 'passed'})
    with pytest.raises(parity.ParityError, match='duplicate or leaked'):
        parity.merge_isolated_chromium676(
            parallel | {next(iter(required)): 'passed'}, required)
    with pytest.raises(parity.ParityError, match='duplicate or leaked'):
        parity.merge_isolated_chromium676(
            parallel | {'__collection__:tests.test_shortcut_buttons_browser676': 'error'},
            required)
    # Outcome differences still fail full parity after merging.
    with pytest.raises(parity.ParityError, match='new_failures=1'):
        parity.compare_reports(
            parallel | required,
            parallel | {**required, next(iter(required)): 'failed'})


def test_751_known_baseline_627_collection_error_requires_recovered_tests(capsys):
    key = parity.LEGACY_627_COLLECTION_ERROR
    prefix = parity.LEGACY_627_SOURCE
    base = {
        key: 'error',
        'tests/test_unrelated.py::test_kept': 'passed',
    }
    candidate = {'tests/test_unrelated.py::test_kept': 'passed'}
    candidate.update({
        prefix + test: 'passed'
        for test in parity.LEGACY_627_REQUIRED_TESTS
    })
    result = parity.compare_reports(base, candidate)
    assert result['inherited_failures'] == 0
    assert result['baseline_cases'] == 2
    assert result['candidate_cases'] == 5
    assert 'RESOLVED_LEGACY_627_COLLECTION_ERROR=VERIFIED' in capsys.readouterr().out

    # Any missing recovered case blocks; no blanket suppression.
    for test in parity.LEGACY_627_REQUIRED_TESTS:
        incomplete = dict(candidate)
        incomplete.pop(prefix + test)
        with pytest.raises(parity.ParityError, match='missing=1'):
            parity.compare_reports(base, incomplete)

    # A failed or skipped replacement must never qualify.
    for outcome in ('failed', 'skipped', 'error'):
        broken = dict(candidate)
        broken[prefix + parity.LEGACY_627_REQUIRED_TESTS[0]] = outcome
        with pytest.raises(parity.ParityError):
            parity.compare_reports(base, broken)

    # All other baseline test identities, including other collection errors,
    # must remain present with their original outcomes.
    for extra in ('__collection__:tests.other_module',
                  'tests/test_unrelated.py::test_lost'):
        with pytest.raises(parity.ParityError, match='missing=1'):
            parity.compare_reports(base | {extra: 'error'}, candidate)

    # Only a genuine baseline collection error can be resolved.
    with pytest.raises(parity.ParityError, match='missing=1'):
        parity.compare_reports(base | {key: 'passed'}, candidate)
    # A baseline module with already-collected tests cannot claim recovery.
    with pytest.raises(parity.ParityError, match='missing=1'):
        parity.compare_reports(base | {prefix + 'test_preexisting': 'passed'},
                               candidate | {prefix + 'test_preexisting': 'passed'})


def test_751_inherited_failure_is_not_a_new_regression():
    base = {"tests/test_a.py::test_one": "failed",
            "tests/test_b.py::test_two": "passed",
            "tests/test_c.py::test_three": "skipped"}
    candidate = base | {"tests/test_new.py::test_four": "passed"}
    report = parity.compare_reports(base, candidate)
    assert report == {"baseline_cases": 3, "candidate_cases": 4,
                      "inherited_failures": 1}


@pytest.mark.parametrize("candidate", [
    {"tests/test_a.py::test_a": "failed", "tests/test_b.py::test_b": "failed"},
    {"tests/test_a.py::test_a": "error", "tests/test_b.py::test_b": "passed"},
    {"tests/test_a.py::test_a": "failed", "tests/test_b.py::test_b": "skipped"},
    {"tests/test_a.py::test_a": "passed"},
])
def test_751_any_new_failure_skip_error_or_missing_test_blocks(candidate):
    base = {"tests/test_a.py::test_a": "failed",
            "tests/test_b.py::test_b": "passed"}
    with pytest.raises(parity.ParityError):
        parity.compare_reports(base, candidate)


def _case(nodeid, classname="legacy", name="same", failure=False):
    evidence = ('<properties><property name="tracker_pytest_nodeid_751" '
                f'value="{nodeid}"/></properties>')
    return (f'<testcase classname="{classname}" name="{name}">'
            f'{evidence}{"<failure/>" if failure else ""}</testcase>')


def test_751_empty_missing_duplicate_or_malformed_nodeids_are_rejected(tmp_path):
    p = tmp_path / "suite.xml"
    p.write_text("<testsuite></testsuite>")
    with pytest.raises(parity.ParityError):
        parity.read_report(p)
    p.write_text('<testsuite><testcase classname="s" name="a"/></testsuite>')
    with pytest.raises(parity.ParityError, match="nodeid property"):
        parity.read_report(p)
    p.write_text('<testsuite>' + _case('tests/test_a.py::test_a')
                 + _case('tests/test_a.py::test_a', name='different')
                 + '</testsuite>')
    with pytest.raises(parity.ParityError, match="duplicate pytest nodeid"):
        parity.read_report(p)
    p.write_text('<testsuite>' + _case('../bad/path::test_a') + '</testsuite>')
    with pytest.raises(parity.ParityError, match="nodeid"):
        parity.read_report(p)
    p.write_text('<testsuite><testcase></testsuite>')
    with pytest.raises(ET.ParseError):
        parity.read_report(p)
    # Collection error records deliberately lack item user-properties.
    p.write_text('<testsuite><testcase classname="" name="tests.test_broken">'
                 '<error message="collection failure">import error</error>'
                 '</testcase></testsuite>')
    assert parity.read_report(p) == {
        '__collection__:tests.test_broken': 'error'
    }
    # Missing properties on an ordinary test remain a hard error.
    p.write_text('<testsuite><testcase classname="module" name="test_case">'
                 '<error message="setup failure"/></testcase></testsuite>')
    with pytest.raises(parity.ParityError, match="nodeid property"):
        parity.read_report(p)


def test_751_distinct_nodeids_do_not_collide_on_junit_display_names(tmp_path):
    # JUnit display metadata may collide; actual pytest nodeids may not.
    p = tmp_path / 'suite.xml'
    p.write_text('<testsuite>'
                 + _case('tests/test_a.py::test_a')
                 + _case('tests/test_b.py::test_b', failure=True)
                 + '</testsuite>')
    assert parity.read_report(p) == {
        'tests/test_a.py::test_a': 'passed',
        'tests/test_b.py::test_b': 'failed',
    }


def test_751_real_pytest_junit_properties_and_collection_errors(tmp_path):
    # Real subprocess evidence catches schema assumptions before the six-minute
    # full backend parity run. Run with xdist just like production qualification.
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_report_smoke.py").write_text(
        "import pytest\n"
        "@pytest.mark.parametrize('number',[1,2])\n"
        "def test_ok(number):\n"
        "    assert number > 0\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        (str(ROOT / "scripts"), env.get("PYTHONPATH", ""))
    )

    def run_case(filename, output):
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "pytest", "-p",
             "tracker_pytest_nodeid751", "-n", "2", "--dist=loadfile",
             "-q", "--junitxml=" + str(output), filename],
            cwd=tmp_path, env=env, capture_output=True,
            text=True, timeout=60, check=False,
        )
        assert output.is_file(), (
            completed.returncode, completed.stdout[-700:],
            completed.stderr[-700:]
        )
        return completed

    passing = tmp_path / "passing.xml"
    completed = run_case("tests/test_report_smoke.py", passing)
    assert completed.returncode == 0, (
        completed.stdout[-700:], completed.stderr[-700:]
    )
    assert parity.read_report(passing) == {
        "tests/test_report_smoke.py::test_ok[1]": "passed",
        "tests/test_report_smoke.py::test_ok[2]": "passed",
    }

    (tests / "test_broken_import.py").write_text(
        "raise RuntimeError('synthetic collection failure')\n"
    )
    broken = tmp_path / "broken.xml"
    completed = run_case("tests/test_broken_import.py", broken)
    assert completed.returncode in (1, 2), (
        completed.stdout[-700:], completed.stderr[-700:]
    )
    assert parity.read_report(broken) == {
        "__collection__:tests.test_broken_import": "error",
    }


def test_751_expanded_supplies_case_keeps_original_baseline_identity():
    # Real case content must become stronger without losing its exact
    # baseline nodeid in the full-suite parity comparison.
    src = (ROOT / "tests/test_core_user_db394.py").read_text()
    assert '"supplies": 9' in src
    assert '"supplies-5"' in src
    assert 'dependencies.count("get_scoped_db390") >= count' in src


def test_751_sanitized_parity_diagnostics_identify_failures_without_params(capsys):
    base = {
        "tests/test_core_user_db394.py::test_every_core_dependency_is_scoped[supplies-5]": "failed",
        "tests/test_workouts655.py::test_655_ui_and_isolation_contract": "passed",
    }
    candidate = {
        "tests/test_core_user_db394.py::test_every_core_dependency_is_scoped[supplies-9]": "passed",
        "tests/test_workouts655.py::test_655_ui_and_isolation_contract": "failed",
    }
    with pytest.raises(parity.ParityError):
        parity.compare_reports(base, candidate)
    error = capsys.readouterr().err
    assert "RELEASE_751_PARITY_MISSING_CASE=tests/test_core_user_db394.py::" in error
    assert "RELEASE_751_PARITY_NEW_FAILURE_CASE=tests/test_workouts655.py::" in error
    assert "supplies-5" not in error and "supplies-9" not in error
    assert "param_sha256_" in error
    assert "FAILED tests/test_core_user_db394.py" in error


def test_751_baseline_gate_is_disposable_and_narrow():
    source = SOURCE.read_text()
    runner = (ROOT / "scripts/tracker-release.sh").read_text()
    qualify = (ROOT / "scripts/tracker-qualify751.sh").read_text()
    assert "TemporaryDirectory(prefix='tracker751-parity.'" in source
    assert "worktree', 'add', '--detach'" in source
    assert "worktree', 'remove', '--force'" in source
    assert "TRACKER_DATA_DIR=str(data)" in source
    assert "source, env=env" in source
    assert "new_skips" in source and "new_failures" in source and "missing" in source
    assert "result.returncode not in (0, 1)" in source
    assert "tracker_pytest_nodeid751" in source
    assert "FOCUSED_BACKEND_TESTS" in source
    assert "CHROMIUM_676_NODEIDS" in source
    assert "merge_isolated_chromium676" in source
    assert "extra_ignores=(CHROMIUM_676_MODULE,)" in source
    assert "(CHROMIUM_676_MODULE,), parallel=False" in source
    assert "RELEASE_751_BACKEND_CHROMIUM_676_ISOLATION=PASSED" in source
    assert "root / 'baseline-focus'" in source
    assert "root / 'candidate-focus'" in source
    assert "RELEASE_751_BACKEND_FOCUSED_PARITY=PASSED" in source
    assert "_safe_case_identifier" in source
    assert "plugin_dir = candidate / 'scripts'" in source
    assert "nodeid in result" in source
    assert "'__collection__:' + name" in source
    assert "collection failure" in source
    assert "RELEASE_751_BACKEND_RUN=" in source
    writer = (ROOT / "scripts/tracker_dev_log577.py").read_text()
    assert "REQUIRED_PARITY_751" in writer
    assert "release=release" in writer
    assert "scripts/tracker_dev_log577.py" in qualify
    assert "tracker_pytest_nodeid_751" in (
        ROOT / "scripts/tracker_pytest_nodeid751.py").read_text()
    assert "timeout=1200" in source
    assert "RELEASE_751_BACKEND_BASELINE_PARITY=PASSED" in source
    assert "--ignore=tests/browser" in runner
    assert "RELEASE_751_BACKEND_BASELINE_PARITY=PASSED" not in runner
    assert "tracker-backend-parity751.py" in runner
    assert "tracker-backend-parity751.py" in qualify
    assert 'timeout 1800 bash "$QA/scripts/tracker-browser-qualify.sh"' in runner
    assert 'timeout 600 bash "$QA/scripts/tracker-browser-qualify.sh"' in runner
