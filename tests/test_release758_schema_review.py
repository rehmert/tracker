"""Release 758 migration review safeguards and backup flag contract."""
from pathlib import Path
import importlib.util
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/tracker_schema_review758.py"
SPEC = importlib.util.spec_from_file_location("tracker_schema_review758", SOURCE)
reviewer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reviewer)
BASE = "90b297fc07c950d5a44a0bf8fe7d4beabfd8b30f"


def test_exact_nullable_schema_declaration_only():
    for line in (reviewer.MODEL_LINE, reviewer.MIGRATION_LINE):
        old = "existing\n"
        assert reviewer.exact_additive(old, old + line, line)
        assert not reviewer.exact_additive(old, old, line)
        assert not reviewer.exact_additive(old, old + line * 2, line)
        assert not reviewer.exact_additive(old, old + line + "unreviewed\n", line)


def test_candidate_schema_has_only_reviewed_additions():
    sha = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
    ).strip()
    reviewer.review(ROOT, BASE, sha)
    with pytest.raises(ValueError):
        reviewer.review(ROOT, sha, sha)


def test_schema_review_is_required_by_guarded_installer():
    install = (ROOT / "scripts/tracker-install758.sh").read_text()
    runner = (ROOT / "scripts/tracker-release.sh").read_text()
    qa = (ROOT / "scripts/tracker-qualify758.sh").read_text()
    assert "--db-migration --reviewed-vial-758" in install
    assert "--reviewed-vial-758) REVIEWED_VIAL_758=1" in runner
    assert "tracker_schema_review758.py" in runner
    assert "VIAL_758_SCHEMA_PROCEDURE=AUTHORIZED" in runner
    assert "Schema changes require verified migration backup" in runner
    assert "Schema changes require a reviewed schema flag" in runner
    assert "tracker_schema_review758.py" in qa
