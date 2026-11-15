"""Release 635 reviewed schema deployment gate is narrowly restricted."""
import ast
from pathlib import Path
import pytest

pytestmark = pytest.mark.quick

ROOT = Path(__file__).resolve().parents[1]


def test_regimen_models_are_only_three_new_tables():
    from app.models import RegimenItem, RegimenSchedule, RegimenEntry
    assert (
        RegimenItem.__tablename__,
        RegimenSchedule.__tablename__,
        RegimenEntry.__tablename__,
    ) == ("regimen_items635", "regimen_schedules635", "regimen_entries635")


def test_reviewed_gate_requires_explicit_migration_backup():
    source = (ROOT / "scripts/tracker-release.sh").read_text()
    assert '--reviewed-regimen-635)' in source
    assert '[[ "$REVIEWED_REGIMEN_635" == 1 && "$DB_MIGRATION" == 1 ]]' in source
    assert '[[ "$INSTANCE" == DEV && "$REF" == release/635-regimen-catalog-schedules' in source
    assert '"$QA/scripts/tracker_schema_review635.py"' in source
    assert 'DATABASE_BACKUP=VERIFIED_FOR_MIGRATION' in source
    assert '"$DEV_FOCUSED_630" "$DB_MIGRATION" "$REVIEWED_REGIMEN_635"' in source


def test_signed_prod_pipeline_opts_into_migration_only_for_635():
    source = (ROOT / "scripts/tracker_prod_remote568.sh").read_text()
    assert 'if [[ "$RELEASE" == 635 ]]; then' in source
    assert 'DEPLOY_EXTRA=(--reviewed-regimen-635 --db-migration)' in source
    assert '"${DEPLOY_EXTRA[@]}"' in source


def test_review_script_rejects_unapproved_source_paths(monkeypatch):
    from scripts import tracker_schema_review635 as m
    def git(_root, *args):
        if args[:2] == ("diff", "--name-only"):
            return "app/models.py\napp/security.py\n"
        raise AssertionError(args)
    monkeypatch.setattr(m, "git", git)
    with pytest.raises(ValueError, match="unapproved changed paths"):
        m.review(ROOT, "base", "target")


def test_review_script_rejects_existing_model_rewrite(monkeypatch):
    from scripts import tracker_schema_review635 as m
    def git(_root, *args):
        if args[:2] == ("diff", "--name-only"):
            return "app/models.py\n"
        if args[:2] == ("show", "base:app/models.py"):
            return "class Existing:\n    x = 1\n"
        if args[:2] == ("show", "target:app/models.py"):
            return "class Existing:\n    x = 2\n"
        raise AssertionError(args)
    monkeypatch.setattr(m, "git", git)
    with pytest.raises(ValueError, match="modified existing model"):
        m.review(ROOT, "base", "target")


def test_review_script_does_not_accept_unexpected_new_tables(monkeypatch):
    from scripts import tracker_schema_review635 as m
    original = "class Existing:\n    x = 1\n"
    new = original + "\nclass Unknown:\n    __tablename__ = 'passwords'\n"
    def git(_root, *args):
        if args[:2] == ("diff", "--name-only"):
            return "app/models.py\n"
        if args[:2] == ("show", "base:app/models.py"):
            return original
        if args[:2] == ("show", "target:app/models.py"):
            return new
        raise AssertionError(args)
    monkeypatch.setattr(m, "git", git)
    with pytest.raises(ValueError, match="Unexpected appended model classes"):
        m.review(ROOT, "base", "target")


def test_no_direct_live_schema_mutation_in_regimen_router():
    router = (ROOT / "app/routers/regimen635.py").read_text()
    tree = ast.parse(router)
    assert not any(
        isinstance(node, ast.Attribute) and node.attr in ("create_all", "drop_all", "exec_driver_sql")
        for node in ast.walk(tree)
    )
