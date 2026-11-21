"""Release 735: one-time PROD 727->735 signed catch-up must fail closed."""
from pathlib import Path
import pytest

from scripts import tracker_schema_review735 as review

ROOT = Path(__file__).resolve().parents[1]


def test_735_exact_727_to_latest_source_history_is_reviewed():
    review.review(ROOT, review.PROD_727, "HEAD")
    assert [number for number, _ in review.MILESTONES] == [
        "729", "730", "731", "732", "733", "734",
    ]
    assert review.SCHEMA_INTRO == "0bc005f9c1e5b1353a67755aeeb2940140a7c74f"


def test_735_wrong_base_and_pre_catchup_target_are_rejected():
    with pytest.raises(ValueError, match="exact installed PROD Release 727"):
        review.review(ROOT, review.DEV_730, "HEAD")
    with pytest.raises(ValueError, match="exact Release 735 target commit"):
        review.review(ROOT, review.PROD_727, review.MILESTONES[-1][1])
    with pytest.raises(ValueError):
        review.review(ROOT, review.PROD_727, "bad-target")


def test_735_prod_runner_requires_signed_exact_source_and_backup():
    runner = (ROOT / "scripts/tracker-release.sh").read_text()
    remote = (ROOT / "scripts/tracker_prod_remote568.sh").read_text()
    promoter = (ROOT / "scripts/tracker_promote568.py").read_text()
    requirements = (
        "REVIEWED_CATCHUP_735",
        '[[ $# -ge 12 && $# -le 22 ]]',
        '--reviewed-catchup-735',
        'RELEASE_735_SCHEMA_CATCHUP_REVIEW=PASSED',
        'tracker_schema_review735.py',
        'Release 735 catch-up restricted to installed PROD 727',
        'Release 735 catch-up requires verified --db-migration backup',
        'Release 735 catch-up must be an isolated PROD-only reviewed schema stage',
        'REVIEWED_TABLET_731" == 0',
        'REVIEWED_CATCHUP_735" == 1',
        '=== Verified database backup required for data migration ===',
        '=== ISOLATED RESTORE VERIFICATION PASSED ===',
    )
    for token in requirements:
        assert token in runner, token
    assert 'DEPLOY_EXTRA=(--reviewed-catchup-735 --db-migration)' in remote
    assert '[[ "$RELEASE" == 735 ]]' in remote
    assert 'Release 735 catch-up requires exact PROD 727 base' in remote
    assert '--instance PROD' in remote and 'DEPLOY_EXTRA[@]' in remote
    assert 'sign_and_transfer(args.target)' in promoter
    assert 'promote(args.target, args.prod_base)' in promoter
    assert 'deploy(args.release, args.target, args.prod_base)' in promoter
    assert 'verified_log(log.read_text(encoding="utf-8"), target)' in promoter


def test_735_cross_release_regimen_and_workout_qa_are_covered():
    scoped = (ROOT / "scripts/tracker-release-scoped735.sh").read_text()
    runner = (ROOT / "scripts/tracker-release.sh").read_text()
    for path in (
        "tests/test_release729_lab_entry_cards.py",
        "tests/test_release730_medication_prefill.py",
        "tests/test_release730_workout_page_queries.py",
        "tests/test_release731_tablet_tracking.py",
        "tests/test_release732_medication_delete.py",
        "tests/test_release733_regimen_macd_actions.py",
        "tests/test_release734_regimen_button_parity.py",
        "tests/test_release735_prod_catchup.py",
    ):
        assert path in scoped
    assert "RELEASE_735_PROD_SCOPED=PASSED" in runner
    assert "--full-suite" not in (
        ROOT / "scripts/tracker_prod_remote568.sh"
    ).read_text()
