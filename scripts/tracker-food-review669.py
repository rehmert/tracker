#!/usr/bin/env python3
"""Exact-source Release 669 food editor review; read-only and fail closed."""
from __future__ import annotations
import argparse
from pathlib import Path
import re
import subprocess

BASE669 = "c5ca4e1e226408b6d5784794dab5f73205b95c36"
MODIFIED669 = frozenset({
    "app/routers/food.py",
    "app/templates/food.html",
    "scripts/tracker-release.sh",
})
NEW669 = frozenset({
    "app/templates/food_saved_edit669.html",
    "tests/test_food_saved_edit669.py",
    "scripts/tracker-food-review669.py",
    "scripts/tracker-release-scoped669.sh",
    "scripts/tracker-preview669.sh",
    "scripts/tracker-release669.sh",
    "docs/release-669-food-editor.md",
})


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        text=True, capture_output=True, check=False,
    )
    if completed.returncode:
        raise ValueError("Git source review failed: " + completed.stderr[:200])
    return completed.stdout


def review(root: Path, base: str, target: str) -> None:
    if base != BASE669 or not re.fullmatch(r"[0-9a-f]{40}", target):
        raise ValueError("Unexpected release baseline or candidate")
    if git(root, "rev-parse", "HEAD").strip() != target:
        raise ValueError("Source checkout is not exact candidate")
    git(root, "merge-base", "--is-ancestor", base, target)
    modified = set(git(root, "diff", "--name-only", base, target).splitlines())
    allowed = MODIFIED669 | NEW669
    marker = "docs/release-669-ready.txt"
    if marker in modified:
        if git(root, "show", f"{target}:{marker}").strip() != (
            "RELEASE_669_IMPLEMENTATION_REVIEWED=YES"
        ):
            raise ValueError("Invalid Release 669 readiness marker")
        allowed = allowed | {marker}
    if modified != allowed:
        raise ValueError(f"Unexpected Release 669 changed paths: {sorted(modified ^ allowed)}")
    old = git(root, "show", f"{base}:app/routers/food.py")
    new = (root / "app/routers/food.py").read_text(encoding="utf-8")
    if not new.startswith(old):
        raise ValueError("Historical food routes or validation modified")
    added = new[len(old):]
    for fragment in (
        '@router.get("/food/saved/{product_id}/edit")',
        '@router.post("/food/saved/{product_id}/edit")',
        "get_food_read_engine406",
        "food_product_version669(row)",
        "required_food_nutrients629",
    ):
        if fragment not in new:
            raise ValueError("Food editor source contract missing: " + fragment)
    if "db_engine.begin()" not in added or "confirm_history" not in added:
        raise ValueError("Saved-food edit requires confirmed atomic update")
    if 'INSERT INTO tracker_food_entries' in added or 'DELETE FROM' in added:
        raise ValueError("Saved-food editing must not change meal history")
    before = git(root, "show", f"{base}:app/templates/food.html")
    after = (root / "app/templates/food.html").read_text(encoding="utf-8")
    links = (
        ' <p><a href="/food/saved/{{ item.id }}/edit?day={{ day }}">Edit Saved Food</a></p>\n',
        '<p><a href="/food/saved/{{ item.id }}/edit?day={{ day }}">Edit Saved Food</a></p>\n',
        ' <a href="/food/saved/{{ e.product_id }}/edit?day={{ day }}">Edit Saved Food</a>\n',
    )
    if after.count(links[0]) != 2 or after.count(links[1]) != 3 or after.count(links[2]) != 1:
        raise ValueError("Saved food navigation links are not present exactly")
    restored = after
    for link in links:
        restored = restored.replace(link, "")
    if restored != before:
        raise ValueError("Saved-food links modified unrelated journal template")
    runner_old = git(root, "show", f"{base}:scripts/tracker-release.sh")
    runner_new = (root / "scripts/tracker-release.sh").read_text(encoding="utf-8")
    hook = """ if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped669.sh |
      grep -qx 'scripts/tracker-release-scoped669.sh'; then
  echo "=== RELEASE 669 PROD FOCUSED FOOD EDITOR QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped669.sh" "$PY"
  echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
 fi
"""
    if runner_new.replace(hook, "") != runner_old:
        raise ValueError("Deployment runner differs outside exact Release 669 PROD test hook")
    print("RELEASE_669_EXACT_SOURCE_REVIEW=PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    review(args.root.resolve(), args.base, args.target)
