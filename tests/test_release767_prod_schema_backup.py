"""Release 767: no PROD data in tests, exact source and prebackup contract."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = ROOT / "scripts/tracker-prod-schema-backup767.py"
REMOTE_PATH = ROOT / "scripts/tracker_prod_remote568.sh"
spec = spec_from_file_location("release767_backup_tested", GUARD_PATH)
assert spec and spec.loader
mod = module_from_spec(spec)
spec.loader.exec_module(mod)


def target_sha():
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def test_767_exact_signed_dev_766_sources_accepted_with_catchup():
    mod.review_source(ROOT, mod.PROD_765, target_sha())
    assert mod.MODEL_TABLE == "device_days766"


@pytest.mark.parametrize("base", ["a" * 40, "", mod.APPROVED_DEV_766])
def test_767_bad_base_rejected_before_any_backup(base):
    with pytest.raises(ValueError):
        mod.review_source(ROOT, base, target_sha())


def test_767_not_allowed_to_downgrade_or_reuse_dev_766_target():
    with pytest.raises(ValueError):
        mod.review_source(ROOT, mod.PROD_765, mod.APPROVED_DEV_766)


def test_767_signed_prod_remote_stages_guard_before_runner():
    content = REMOTE_PATH.read_text(encoding="utf-8")
    start = content.index('if [[ "$RELEASE" == 767 ]]')
    guard = content.index('PYTHONPATH="$APP" "$APP/.venv/bin/python" "$BACKUP_GUARD"')
    runner = content.index('bash "$RUNNER"')
    assert start < guard < runner
    assert '[[ "$BASE" == 8c67580611fd945d9ae83f8015f071a24ab6fee5 ]]' in content
    assert 'git show "$TARGET:$BACKUP_REL"' in content
    assert '"$(git hash-object "$BACKUP_GUARD")" == "$EXPECTED_BACKUP"' in content
    assert "RELEASE_767_PROD_SCHEMA_BACKUP=PASSED" in content
    assert "RELEASE_767_PROD_DATABASE_SNAPSHOT=VERIFIED" in GUARD_PATH.read_text()
    assert "RELEASE_767_PROD_SQLITE_UPLOAD_RESTORE=PASSED" in GUARD_PATH.read_text()


def test_767_backup_refuses_every_nonprod_host_before_live_io(tmp_path):
    with pytest.raises(ValueError):
        mod.run_verified(tmp_path, mod.PROD_765, target_sha())


def test_767_only_release_script_test_and_docs_changed_since_dev_766():
    delta = subprocess.check_output(
        ["git", "diff", "--name-only", mod.APPROVED_DEV_766, target_sha()],
        cwd=ROOT, text=True
    ).splitlines()
    assert delta
    assert all(
        p.startswith(("scripts/", "tests/", "docs/")) for p in delta
    )
    assert not any(p.startswith("app/") for p in delta)


def test_767_backup_strict_integrity_complete_archive_and_pruning_contract():
    content = GUARD_PATH.read_text(encoding="utf-8")
    for required in (
        "tracker-attachment-integrity645.py", "--hashes",
        "from app.backup import create_backup, verify_backup",
        "tracker-restore-verify.py",
        "verify_pre_schema_database(data)",
        "archive.is_symlink()", "archives[10:]",
        "destination.chmod(0o700)", "archive.chmod(0o600)",
    ):
        assert required in content
    assert "git(root, \"merge-base\", \"--is-ancestor\", APPROVED_DEV_766, target)" in content
