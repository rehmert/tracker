"""Release 446: integration tests for read-only cross-branch promotion audit.

All Git changes take place in fresh tmp_path fixture repositories. Tests
never mutate the current Tracker checkout or access any SQLite database.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "tracker-promotion-audit446.py"


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=30,
    )
    return result.stdout.strip()


def put(root, path, content):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


@pytest.fixture
def branches(tmp_path):
    root = tmp_path / "audit-repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.name", "Tracker test")
    git(root, "config", "user.email", "test@example.invalid")

    put(root, "app/routers/food.py", "# common food source\n")
    put(root, "app/main.py", "# shared app entrypoint\n")
    put(root, "app/templates/vial_labels423.html", "original labels\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "common origin")
    common = git(root, "rev-parse", "HEAD")
    git(root, "branch", "prod")

    put(root, "app/secondary_preview430.py", "# isolated gateway\n")
    put(root, "tests/test_secondary_preview430.py", "# isolated tests\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "secondary preview only")
    secondary_sha = git(root, "rev-parse", "HEAD")

    put(root, "app/main.py",
        "# shared app entrypoint\n# secondary gateway mount\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "shared entrypoint requires review")
    dev = git(root, "rev-parse", "HEAD")
    git(root, "branch", "dev")
    git(root, "checkout", "-q", "prod")

    put(root, "app/templates/vial_labels423.html", "updated prod label\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "production label improvement")
    prod = git(root, "rev-parse", "HEAD")

    return {
        "repo": root, "prod": prod, "dev": dev,
        "common": common, "secondary_sha": secondary_sha,
    }


def cli(branches, *args, expected=0):
    root = branches["repo"]
    run = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--repo", str(root), "--prod-ref", "prod",
            "--dev-ref", "dev", *args,
        ],
        check=False, capture_output=True, text=True, timeout=45,
    )
    assert run.returncode == expected, (
        f"code={run.returncode}\nstdout={run.stdout}\nstderr={run.stderr}"
    )
    return run


def test_branch_divergence_is_reported_from_actual_git_history(branches):
    report = json.loads(cli(branches, "--format", "json").stdout)
    assert report["audit_version"] == 446
    assert report["prod_sha"] == branches["prod"]
    assert report["dev_sha"] == branches["dev"]
    assert report["merge_base"] == branches["common"]
    assert report["prod_only_commit_count"] == 1
    assert report["dev_only_commit_count"] == 2
    assert report["actual_differing_file_count"] == 4
    assert report["safe_to_promote_automatically"] is False
    assert report["deployment_performed"] is False
    assert report["prod_only_commits"][0]["subject"] == "production label improvement"
    assert report["dev_only_commits"][0]["sha"] == branches["secondary_sha"]
    assert "likely-secondary-only" in report["dev_only_commits"][0]["review_categories"]
    assert "shared-entrypoint-review" in report["dev_only_commits"][1]["review_categories"]


def test_classifies_secondary_shared_and_general_changes(branches):
    report = json.loads(cli(branches, "--format", "json").stdout)
    files = {x["path"]: x for x in report["files"]}
    assert set(files) == {
        "app/main.py",
        "app/secondary_preview430.py",
        "tests/test_secondary_preview430.py",
        "app/templates/vial_labels423.html",
    }
    assert files["app/main.py"]["category"] == "shared-entrypoint-review"
    assert files["app/main.py"]["status"] == "M"
    assert files["app/secondary_preview430.py"]["category"] == "likely-secondary-only"
    assert files["app/secondary_preview430.py"]["status"] == "A"
    assert files["tests/test_secondary_preview430.py"]["category"] == "likely-secondary-only"
    assert files["app/templates/vial_labels423.html"]["category"] == "general-feature-review"
    assert files["app/templates/vial_labels423.html"]["status"] == "M"
    assert report["category_counts"] == {
        "likely-secondary-only": 2,
        "shared-entrypoint-review": 1,
        "general-feature-review": 1,
        "audit-tooling-review": 0,
    }


def test_core_feature_status_looks_at_source_contents_not_release_numbers(branches):
    report = json.loads(cli(branches, "--format", "json").stdout)
    features = {x["path"]: x["status"] for x in report["core_features"]}
    assert features["app/routers/food.py"] == "identical"
    assert features["app/templates/vial_labels423.html"] == "different"
    assert features["app/routers/doses.py"] == "absent-both"
    assert features["app/templates/base.html"] == "absent-both"


def test_readable_text_report_discloses_unsafe_automatic_promotion(branches):
    result = cli(branches)
    assert "PROD_ONLY_COMMITS=1" in result.stdout
    assert "DEV_ONLY_COMMITS=2" in result.stdout
    assert "ACTUAL_DIFFERING_FILES=4" in result.stdout
    assert "shared-entrypoint-review" in result.stdout
    assert "=== DEV-ONLY COMMITS ===" in result.stdout
    assert "SAFE_TO_PROMOTE_AUTOMATICALLY=NO" in result.stdout
    assert "DEPLOYED=NO" in result.stdout


def test_source_tree_and_git_head_are_unchanged_by_reporting(branches):
    repo = branches["repo"]
    before = git(repo, "status", "--porcelain")
    head = git(repo, "rev-parse", "HEAD")
    refs = git(repo, "show-ref")
    cli(branches, "--format", "json")
    cli(branches)
    assert git(repo, "status", "--porcelain") == before == ""
    assert git(repo, "rev-parse", "HEAD") == head
    assert git(repo, "show-ref") == refs
    assert (repo / "app/main.py").read_text() == "# shared app entrypoint\n"


def test_same_branch_produces_zero_differences(branches):
    run = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--repo", str(branches["repo"]),
            "--prod-ref", "prod", "--dev-ref", "prod", "--format", "json",
        ],
        capture_output=True, text=True, check=True, timeout=45,
    )
    report = json.loads(run.stdout)
    assert report["actual_differing_file_count"] == 0
    assert report["prod_only_commit_count"] == 0
    assert report["dev_only_commit_count"] == 0
    assert report["files"] == []
    assert all(value == 0 for value in report["category_counts"].values())


@pytest.mark.parametrize(
    "invalid", (
        "--bad", "HEAD..prod", "foo//bar", "origin/main.lock",
        "branch/@{1}", "branch/", "broken\nname",
    ),
)
def test_unsafe_refs_are_rejected(branches, invalid):
    result = cli(
        branches, "--dev-ref=" + invalid, expected=1,
    )
    assert "Unsafe Git reference" in result.stderr


def test_unavailable_ref_fails_without_guessing_or_fetching(branches):
    result = cli(branches, "--dev-ref=origin/not-fetched", expected=1)
    assert "Git audit command failed" in result.stderr
    assert "git fetch" not in result.stdout


def test_repo_must_be_checkout_root(branches):
    root = branches["repo"]
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--repo", str(root / "app"),
            "--prod-ref", "prod", "--dev-ref", "dev",
        ],
        capture_output=True, text=True, check=False, timeout=45,
    )
    assert result.returncode == 1
    assert "working-tree root" in result.stderr


def test_all_secondary_path_families_and_reporting_paths_are_classified():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "tracker_promotion_audit446", SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    secondary = (
        "app/worker_supply_use439.py",
        "app/user_accounts427.py",
        "app/user_bootstrap426.py",
        "scripts/tracker-secondary-ops443.py",
        "scripts/tracker-worker-probe428.py",
        "scripts/tracker-stage-user426.py",
        "tests/test_worker_scope428.py",
    )
    assert all(module.classify(path) == "likely-secondary-only"
               for path in secondary)
    assert module.classify("app/main.py") == "shared-entrypoint-review"
    assert module.classify("app/routers/food.py") == "general-feature-review"
    assert module.classify("scripts/tracker-promotion-audit446.py") == "audit-tooling-review"
    assert module.classify("tests/test_promotion_audit446.py") == "audit-tooling-review"


def test_current_checkout_never_emits_destructive_git_operations():
    source = SCRIPT.read_text()
    for forbidden in (
        '"reset"', '"checkout"', '"merge"', '"push"',
        '"pull"', '"clean"', '"fetch"', '"switch"',
    ):
        assert forbidden not in source
    assert "sqlite3" not in source
    assert "subprocess.run" in source
    assert "safe_to_promote_automatically" in source
