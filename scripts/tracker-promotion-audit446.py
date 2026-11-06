#!/usr/bin/env python3
"""Release 446: read-only DEV-versus-PROD source and commit promotion audit.

Only local Git object metadata is read. No fetch, checkout, deployment,
database access, filesystem modifications, or automatic promotions.
Path classifications are REVIEW HINTS, not evidence of promotion safety.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

VERSION = 446
CORE_PATHS = (
    "app/routers/food.py",
    "app/routers/doses.py",
    "app/routers/vitals.py",
    "app/routers/calendar.py",
    "app/routers/vials.py",
    "app/templates/food.html",
    "app/templates/doses.html",
    "app/templates/vitals.html",
    "app/templates/calendar.html",
    "app/templates/vial_labels423.html",
    "app/vial_label_rotation431.py",
    "app/templates/base.html",
)
SECONDARY_FILE_NAMES = {
    "app/user_accounts427.py",
    "app/user_bootstrap426.py",
    "tests/test_user_accounts427.py",
    "tests/test_user_bootstrap426.py",
}
SECONDARY_PREFIXES = (
    "app/secondary_",
    "app/worker_",
    "scripts/tracker-secondary-",
    "scripts/tracker-stage-",
    "scripts/tracker-worker-",
    "tests/test_secondary_",
    "tests/test_worker_",
)
AUDIT_TOOLING = {
    "scripts/tracker-promotion-audit446.py",
    "tests/test_promotion_audit446.py",
}
REF_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./-]{0,160}\Z")


class AuditError(ValueError):
    pass


def git(repo: Path, *args: str) -> bytes:
    command = ["git", "-c", f"safe.directory={repo}", "-C", str(repo), *args]
    result = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False, timeout=60,
    )
    if result.returncode:
        raise AuditError("Git audit command failed: " + str(args[0]))
    return result.stdout


def _ref(repo: Path, value: str) -> str:
    if (not isinstance(value, str)
        or not REF_PATTERN.fullmatch(value)
        or ".." in value or "//" in value or value.endswith(".lock")
        or value.endswith("/") or "/." in value):
        raise AuditError("Unsafe Git reference")
    value = value + "^{commit}"
    sha = git(repo, "rev-parse", "--verify", "--end-of-options", value)
    resolved = sha.decode("ascii").strip()
    if not re.fullmatch(r"[a-f0-9]{40}", resolved):
        raise AuditError("Git reference did not resolve to a commit")
    return resolved


def _lines(data: bytes) -> list[str]:
    return [x.decode("utf-8", "replace") for x in data.splitlines() if x]


def _diff_files(repo: Path, left: str, right: str) -> list[dict]:
    # --no-renames ensures an edited/renamed file is explicitly audited at
    # both locations. NUL-delimited Git output preserves unusual filenames.
    raw = git(repo, "diff", "--name-status", "--no-renames", "-z",
              left, right, "--")
    parts = raw.split(b"\x00")
    if parts[-1] != b"":
        raise AuditError("Incomplete Git diff output")
    parts.pop()
    if len(parts) % 2:
        raise AuditError("Invalid Git name-status output")
    result = []
    for i in range(0, len(parts), 2):
        status = parts[i].decode("ascii")
        path = parts[i + 1].decode("utf-8", "replace")
        if status not in {"A", "M", "D", "T", "U"} or not path:
            raise AuditError("Unexpected Git diff entry")
        result.append({
            "path": path, "status": status, "category": classify(path),
        })
    return sorted(result, key=lambda entry: entry["path"])


def classify(path: str) -> str:
    """Conservative hints only. Any shared source requires human review."""
    if path in AUDIT_TOOLING:
        return "audit-tooling-review"
    if path == "app/main.py":
        return "shared-entrypoint-review"
    if path in SECONDARY_FILE_NAMES or path.startswith(SECONDARY_PREFIXES):
        return "likely-secondary-only"
    return "general-feature-review"


def _commits(repo: Path, begin: str, end: str) -> list[dict]:
    commits = _lines(git(repo, "rev-list", "--reverse", f"{begin}..{end}"))
    if len(commits) > 2000:
        raise AuditError("More than 2000 commits; narrow the audit range")
    result = []
    for sha in commits:
        subject = git(repo, "show", "-s", "--format=%s", sha).decode(
            "utf-8", "replace"
        ).strip()
        paths = _lines(git(
            repo, "diff-tree", "--root", "--no-commit-id",
            "--name-only", "--no-renames", "-r", sha,
        ))
        categories = sorted({classify(path) for path in paths})
        result.append({
            "sha": sha, "subject": subject, "changed_file_count": len(paths),
            "review_categories": categories or ["merge-or-empty-review"],
        })
    return result


def _exists_at(repo: Path, sha: str, path: str) -> bool:
    # All CORE_PATHS are trusted static literal filenames.
    result = subprocess.run(
        ["git", "-c", f"safe.directory={repo}", "-C", str(repo),
         "cat-file", "-e", f"{sha}:{path}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False, timeout=30,
    )
    return result.returncode == 0


def audit(repo: Path, prod_ref: str, dev_ref: str) -> dict:
    repo = Path(repo).absolute()
    actual_root = Path(git(repo, "rev-parse", "--show-toplevel")
                       .decode("utf-8", "replace").strip()).absolute()
    if actual_root != repo:
        raise AuditError("--repo must be the Git working-tree root")

    prod = _ref(repo, prod_ref)
    dev = _ref(repo, dev_ref)
    ancestor = git(repo, "merge-base", prod, dev).decode("ascii").strip()
    if not re.fullmatch(r"[a-f0-9]{40}", ancestor):
        raise AuditError("Could not identify a common ancestor")

    files = _diff_files(repo, prod, dev)
    prod_only = _commits(repo, dev, prod)
    dev_only = _commits(repo, prod, dev)
    category_counts = {
        name: sum(item["category"] == name for item in files)
        for name in (
            "likely-secondary-only",
            "shared-entrypoint-review",
            "general-feature-review",
            "audit-tooling-review",
        )
    }
    changed = {entry["path"] for entry in files}
    core = []
    for path in CORE_PATHS:
        left = _exists_at(repo, prod, path)
        right = _exists_at(repo, dev, path)
        if not left and not right:
            status = "absent-both"
        elif not left:
            status = "missing-in-prod"
        elif not right:
            status = "missing-in-dev"
        else:
            status = "different" if path in changed else "identical"
        core.append({"path": path, "status": status})

    return {
        "audit_version": VERSION,
        "prod_ref": prod_ref, "prod_sha": prod,
        "dev_ref": dev_ref, "dev_sha": dev,
        "merge_base": ancestor,
        "prod_only_commit_count": len(prod_only),
        "dev_only_commit_count": len(dev_only),
        "actual_differing_file_count": len(files),
        "category_counts": category_counts,
        "core_features": core,
        "files": files, "prod_only_commits": prod_only,
        "dev_only_commits": dev_only,
        "safe_to_promote_automatically": False,
        "deployment_performed": False,
        "notice": (
            "Path categories are hints only. A common filename or commit "
            "message never proves behavioral equivalence or promotion safety."
        ),
    }


def render_text(result: dict) -> str:
    lines = [
        "=== TRACKER PROMOTION AUDIT 446 (READ-ONLY) ===",
        "PROD_SHA=" + result["prod_sha"],
        "DEV_SHA=" + result["dev_sha"],
        "COMMON_ANCESTOR=" + result["merge_base"],
        "PROD_ONLY_COMMITS=" + str(result["prod_only_commit_count"]),
        "DEV_ONLY_COMMITS=" + str(result["dev_only_commit_count"]),
        "ACTUAL_DIFFERING_FILES=" + str(result["actual_differing_file_count"]),
        "=== CATEGORY COUNTS (REVIEW HINTS) ===",
    ]
    lines += [
        f"{name}={count}"
        for name, count in result["category_counts"].items()
    ]
    lines += ["=== CORE SINGLE-USER FEATURE FILES ==="]
    lines += [
        f"{item['status']:18} {item['path']}"
        for item in result["core_features"]
    ]
    lines += ["=== FILE-LEVEL DIFFERENCES ==="]
    lines += [
        f"{item['status']} {item['category']:27} {item['path']}"
        for item in result["files"]
    ]
    for field, title in (
        ("prod_only_commits", "PROD-ONLY COMMITS"),
        ("dev_only_commits", "DEV-ONLY COMMITS"),
    ):
        lines.append("=== " + title + " ===")
        lines += [
            f"{entry['sha'][:12]} [{','.join(entry['review_categories'])}] "
            + entry["subject"]
            for entry in result[field]
        ]
    lines += [
        "SAFE_TO_PROMOTE_AUTOMATICALLY=NO",
        "DEPLOYED=NO",
        "NOTE: File names and commit subjects do not prove behavioral parity.",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--prod-ref", default="origin/main")
    parser.add_argument("--dev-ref", default="HEAD")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        report = audit(args.repo, args.prod_ref, args.dev_ref)
    except (AuditError, OSError, subprocess.TimeoutExpired) as exc:
        print("ERROR: Promotion audit: " + str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
