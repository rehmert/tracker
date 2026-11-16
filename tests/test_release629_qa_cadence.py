"""Historical 629 checks plus Release 652 operator-only full-suite policy.

This checks deployment source only; it never starts the live release worker.
"""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "scripts/tracker-release.sh"
FOCUSED = ROOT / "scripts/tracker-focused-regression604.sh"


def test_629_release_and_focused_shell_parse():
    for path in (RELEASE, FOCUSED):
        result = subprocess.run(["bash", "-n", str(path)],
                                capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, (path, result.stderr)


def test_652_full_regression_requires_explicit_operator_opt_in():
    source = RELEASE.read_text()
    assert 'QA_FULL_REQUIRED="$FULL_SUITE"' in source
    assert '--full-suite) FULL_SUITE=1; shift;;' in source
    assert '"$REVIEWED_COA_652" "$FULL_SUITE"' in source
    assert '10#$RELEASE_SEQUENCE % 5 == 0' not in source
    assert 'QA_CADENCE_REASON="explicit operator full-suite request"' in source
    assert 'RELEASE_SCOPED_PREFLIGHT=PASSED' in source
    assert 'tracker-release-scoped' in source
    assert 'if (( QA_FULL_REQUIRED == 1 )); then' in source
    assert '=== Source and configuration recovery snapshot ===' in source
    assert 'DATABASE_BACKUP=VERIFIED_FOR_MIGRATION' in source
    assert 'tracker-runtime-smoke.py' in source
    assert 'QUALIFICATION_COMPLETE=1' in source



def test_629_periodic_milestones_are_630_635_640_and_so_on():
    # Verify Bash's actual arithmetic, including a leading-zero release.
    program = (
        'for n in 628 629 630 631 634 635 639 640 00630; do '
        'if (( 10#$n % 5 == 0 )); then printf "%s:FULL\\n" "$n"; '
        'else printf "%s:FOCUSED\\n" "$n"; fi; done'
    )
    outcome = subprocess.run(["bash", "-c", program], capture_output=True,
                             text=True, timeout=10, check=True)
    assert outcome.stdout.splitlines() == [
        "628:FOCUSED", "629:FOCUSED", "630:FULL", "631:FOCUSED",
        "634:FOCUSED", "635:FULL", "639:FOCUSED", "640:FULL",
        "00630:FULL",
    ]


def test_629_resource_ceiling_and_parallel_focus_are_preserved():
    source = RELEASE.read_text()
    focused = FOCUSED.read_text()
    assert 'MEMORY_PROPERTY="MemoryMax=16G"' in source
    assert 'TEST_PYTEST_EXTRA=(-n 16 --dist=loadfile)' in source
    assert '"$PY" -m pytest -n 16 --dist=loadfile' in focused
    assert 'tests/test_release_workflow.py' in focused
    assert 'tests/test_release629_qa_cadence.py' in focused
    assert 'tests/test_release629_food_duplicates.py' in focused
    assert 'tests/test_release621_csrf_form_crosswalk.py' not in focused
