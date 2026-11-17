"""Release 668 guarded release worker and PROD scoped QA shape regressions."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_668_worker_accepts_exactly_18_schema_release_arguments():
    source = (ROOT / "scripts/tracker-release.sh").read_text()
    assert 'REVIEWED_WORKOUT_668="${18:-0}"' in source
    assert '[[ $# -ge 12 && $# -le 18 ]] || fail "Bad worker arguments"' in source
    assert '"$REVIEWED_WORKOUT_667" "$REVIEWED_WORKOUT_668"' in source


def test_668_reviewed_prod_branch_runs_exact_scoped_gate():
    source = (ROOT / "scripts/tracker-release.sh").read_text()
    assert re.search(
        r'if \[\[ "\$INSTANCE" == PROD && "\$REVIEWED_WORKOUT_668" == 1 \]\]; then'
        r'[\s\S]{0,200}timeout 360 bash "\$QA/scripts/tracker-release-scoped668.sh" "\$PY"',
        source,
    )
    remote = (ROOT / "scripts/tracker_prod_remote568.sh").read_text()
    assert 'DEPLOY_EXTRA=(--reviewed-workout-668 --db-migration)' in remote
