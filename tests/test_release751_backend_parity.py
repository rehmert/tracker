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
    base = {("case", "a"): "failed", ("case", "b"): "passed",
            ("case", "c"): "skipped"}
    candidate = dict(base, **{}) | {("case", "new"): "passed"}
    report = parity.compare_reports(base, candidate)
    assert report == {"baseline_cases": 3, "candidate_cases": 4,
                      "inherited_failures": 1}


@pytest.mark.parametrize("candidate", [
    {("case", "a"): "failed", ("case", "b"): "failed"},
    {("case", "a"): "error", ("case", "b"): "passed"},
    {("case", "a"): "failed", ("case", "b"): "skipped"},
    {("case", "a"): "passed"},
])
def test_751_any_new_failure_skip_error_or_missing_test_blocks(candidate):
    base = {("case", "a"): "failed", ("case", "b"): "passed"}
    with pytest.raises(parity.ParityError):
        parity.compare_reports(base, candidate)


def test_751_empty_duplicate_or_malformed_evidence_is_rejected(tmp_path):
    p = tmp_path / "suite.xml"
    p.write_text("<testsuite></testsuite>")
    with pytest.raises(parity.ParityError):
        parity.read_report(p)
    p.write_text(
        '<testsuite><testcase classname="s" name="a"/>'
        '<testcase classname="s" name="a"/></testsuite>'
    )
    with pytest.raises(parity.ParityError):
        parity.read_report(p)
    p.write_text(
        '<testsuite><testcase classname="s" name="a"/>'
        '<testcase classname="s" name="b"><failure/></testcase>'
        '</testsuite>'
    )
    assert parity.read_report(p) == {("s", "a"): "passed",
                                    ("s", "b"): "failed"}


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
    assert "timeout=1200" in source
    assert "RELEASE_751_BACKEND_BASELINE_PARITY=PASSED" in source
    assert "--ignore=tests/browser" in runner
    assert "RELEASE_751_BACKEND_BASELINE_PARITY=PASSED" not in runner
    assert "tracker-backend-parity751.py" in runner
    assert "tracker-backend-parity751.py" in qualify
    assert 'timeout 1800 bash "$QA/scripts/tracker-browser-qualify.sh"' in runner
    assert 'timeout 600 bash "$QA/scripts/tracker-browser-qualify.sh"' in runner
