"""Release 691: fail-closed DEV/PROD deployment argument and backup gates.

Source-only checks on the signed release files. Never contacts PROD or changes
installed code, databases, uploads, GitHub main, or CSRF policy.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_691_worker_accepts_exact_19_arguments_with_reviewer_slot():
    runner = _read("scripts/tracker-release.sh")
    assert '[[ $# -ge 12 && $# -le 19 ]] || fail "Bad worker arguments"' in runner
    assert re.search(
        r'REVIEWED_WORKOUT_668="\$\{18:-0\}"; REVIEWED_COA_691="\$\{19:-0\}"',
        runner,
    )
    launch_line = next(
        x for x in runner.splitlines()
        if x.lstrip().startswith('/bin/bash "$RUN/worker.sh" --worker')
    )
    assert launch_line.count('"$REVIEWED_COA_691"') == 1
    assert launch_line.endswith('"$REVIEWED_COA_691"')
    assert '[[ "$REVIEWED_COA_691" == 0 || "$DB_MIGRATION" == 1 ]]' in runner
    assert 'RELEASE_691_SCHEMA_REVIEW' not in runner  # checked via guarded tool, not a bypass
    assert '"$QA/scripts/tracker_schema_review691.py" --root "$APP"' in runner


def test_691_prod_remote_must_request_migration_and_is_signed_target_bound():
    source = _read("scripts/tracker_prod_remote568.sh")
    assert 'elif [[ "$RELEASE" == 691 ]]; then' in source
    branch = source.split('elif [[ "$RELEASE" == 691 ]]; then', 1)[1]
    assert 'DEPLOY_EXTRA=(--reviewed-coa-691 --db-migration)' in branch.split("\nfi\n", 1)[0]
    assert '"$TARGET:scripts/tracker-release.sh"' in source
    assert 'EXPECTED_RUNNER="$(git rev-parse "$TARGET:scripts/tracker-release.sh")"' in source
    assert 'git hash-object "$RUNNER"' in source
    assert '/usr/local/sbin/tracker-verify-dev-approval "$TARGET"' in source
    assert 'git rev-parse origin/main' in source
    assert 'git merge-base --is-ancestor "$BASE" "$TARGET"' in source
    assert '[[ "$HEAD" == "$BASE" ]]' in source
    assert 'grep -Fxq \'EXIT_STATUS=0\' "$LOG"' in source


def test_691_prod_scoped_tests_and_backup_before_source_install():
    runner = _read("scripts/tracker-release.sh")
    assert 'if [[ "$INSTANCE" == PROD && "$REVIEWED_COA_691" == 1 ]]; then' in runner
    assert 'timeout 360 bash "$QA/scripts/tracker-release-scoped691.sh" "$PY"' in runner
    assert 'COA_691_PROD_FOCUSED_TESTS=PASSED' in runner
    assert 'DEV_BACKUP=VERIFIED_SQLITE_AND_ALL_PRESENT_UPLOADS' in runner
    assert 'DATABASE_BACKUP=VERIFIED_FOR_MIGRATION' in runner
    assert '=== ISOLATED RESTORE VERIFICATION PASSED ===' in runner
    assert runner.index('=== Verified database backup required for data migration ===') < (
        runner.index('=== Install via fast-forward ===')
    )
    assert 'g merge --ff-only "$TARGET"' in runner
    assert 'systemctl restart tracker' in runner
    assert 'RELEASE_SCOPED_PREFLIGHT=PASSED' in runner
