"""Release 643 COA-only additive schema and reviewed deployment gate."""
from pathlib import Path
import pytest

from scripts import tracker_schema_review643 as reviewer

ROOT = Path(__file__).resolve().parents[1]


def test_643_one_append_only_coa_document_table():
    from app.models import CoaDocument643
    assert CoaDocument643.__tablename__ == "coa_documents643"
    assert reviewer.review(ROOT,
        "92f6193f509abcb12fd4c9a2f4c8d11854822044", "HEAD")


def test_643_review_rejects_unapproved_changes(monkeypatch):
    def git(_root, *args):
        if args[:2] == ("diff", "--name-only"):
            return "app/models.py\napp/security.py\n"
        raise AssertionError(args)
    monkeypatch.setattr(reviewer, "git", git)
    with pytest.raises(ValueError, match="Unapproved"):
        reviewer.review(ROOT, "base", "target")


def test_643_review_rejects_existing_model_change(monkeypatch):
    def git(_root, *args):
        if args[:2] == ("diff", "--name-only"):
            return "app/models.py\n"
        if args[:2] == ("show", "base:app/models.py"):
            return "class Existing:\n    x = 1\n"
        if args[:2] == ("show", "target:app/models.py"):
            return "class Existing:\n    x = 2\n"
        raise AssertionError(args)
    monkeypatch.setattr(reviewer, "git", git)
    with pytest.raises(ValueError, match="Existing model"):
        reviewer.review(ROOT, "base", "target")


def test_643_prod_must_explicitly_verify_schema_and_backup():
    deployer = (ROOT / "scripts/tracker-release.sh").read_text()
    remote = (ROOT / "scripts/tracker_prod_remote568.sh").read_text()
    assert "--reviewed-coa-643" in deployer
    assert '[[ "$REVIEWED_COA_643" == 0 || "$DB_MIGRATION" == 1 ]]' in deployer
    assert '"$QA/scripts/tracker_schema_review643.py"' in deployer
    assert 'DATABASE_BACKUP=VERIFIED_FOR_MIGRATION' in deployer
    assert 'QA_CADENCE_REASON="reviewed COA upload schema and attachment security change"' in deployer
    assert 'DEPLOY_EXTRA=(--reviewed-coa-643 --db-migration)' in remote
    assert 'tracker-verify-dev-approval "$TARGET"' in remote
