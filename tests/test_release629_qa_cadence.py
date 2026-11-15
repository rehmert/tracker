"""Release 628/629: mandatory focused QA, five-release full QA cadence.

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


def test_629_fifth_release_cadence_and_exceptions_are_fail_closed():
    source = RELEASE.read_text()
    assert 'QA_FULL_REQUIRED=1' in source
    assert 'if [[ "$REF" =~ ^release/([0-9]+)- ]]; then' in source
    assert '10#$RELEASE_SEQUENCE % 5 == 0' in source
    assert 'QA_FULL_REQUIRED=0' in source
    assert 'QA_CADENCE_REASON="fifth release milestone"' in source
    assert 'QA_CADENCE_REASON="security-sensitive source or route changed"' in source
    assert 'QA_CADENCE_REASON="release sequence not recognized"' in source
    assert 'QA_CADENCE_REASON="PROD requires full qualification"' in source
    assert 'if (( QA_FULL_REQUIRED == 1 )); then' in source
    assert 'FOCUSED_RELEASE_GATE=PASSED' in source
    assert 'timeout 180 bash "$QA/scripts/tracker-focused-regression604.sh" "$PY"' in source
    assert source.index('RELEASE 604 FOCUSED REGRESSION') < source.index(
        'if (( QA_FULL_REQUIRED == 1 )); then')
    assert source.index('if (( QA_FULL_REQUIRED == 1 )); then') < source.index(
        '=== COMPLETE REGRESSION SUITE ===')
    assert '=== Source and configuration recovery snapshot ===' in source
    assert 'DATABASE_BACKUP=SKIPPED_NO_MIGRATION' in source
    assert 'DATABASE_BACKUP=VERIFIED_FOR_MIGRATION' in source
    assert '=== ISOLATED RESTORE VERIFICATION PASSED ===' in source
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
