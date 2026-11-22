"""Release 751: full backend legacy-baseline parity remains fail-closed."""
import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/tracker-backend-parity751.py"
spec = importlib.util.spec_from_file_location("tracker_parity751", SOURCE)
parity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)


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
    assert "plugin_dir = candidate / 'scripts'" in source
    assert "nodeid in result" in source
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
