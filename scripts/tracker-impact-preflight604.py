#!/usr/bin/env python3
"""Fail closed on stale positive asset-version tests before a release gate.

Read-only, stdlib only. Examines exact base..target diffs inside an isolated
candidate worktree; never touches running services or application data.
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

SHA = re.compile(r"^[a-f0-9]{40}$")
ASSET = re.compile(
    r'<(?:script|link)\b[^>]*?\b(?:src|href)\s*=\s*["\'](/static/[^"\']+)["\']',
    re.IGNORECASE | re.DOTALL,
)


def git(root: Path, *args: str, missing_ok: bool = False) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        if missing_ok and result.returncode == 128:
            return ""
        raise RuntimeError(
            f"git {args[0]} failed ({result.returncode}): "
            f"{result.stderr.strip()[:350]}"
        )
    return result.stdout


def asset_refs(text: str) -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {}
    for match in ASSET.finditer(text):
        url = match.group(1)
        parsed = urlsplit(url)
        if "{{" in url or "{%" in url or not parsed.path.startswith("/static/"):
            continue
        refs.setdefault(parsed.path, set()).add(url)
    return refs


def stale_positive_assertion(text: str, needle: str) -> bool:
    """Ignore historical/negative fixtures; detect positive literal contracts."""
    if needle not in text:
        return False
    try:
        tree = ast.parse(text)
    except SyntaxError:
        # Broken tests must fail separately at compile time.
        return False

    def contains(node: ast.AST, value: str) -> bool:
        return any(
            isinstance(item, ast.Constant) and item.value == value
            for item in ast.walk(node)
        )

    def requires(node: ast.AST, value: str) -> bool:
        return any(
            isinstance(item, ast.Compare)
            and any(isinstance(op, ast.In) for op in item.ops)
            and contains(item.left, value)
            for item in ast.walk(node)
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Assert) and requires(node.test, needle):
            return True
        if isinstance(node, ast.For) and contains(node.iter, needle):
            if isinstance(node.target, ast.Name):
                bound = node.target.id
                # Loop marker cases: for marker in (...): assert marker in markup
                for child in node.body:
                    if isinstance(child, ast.Assert) and any(
                        isinstance(test, ast.Compare)
                        and any(isinstance(op, ast.In) for op in test.ops)
                        and isinstance(test.left, ast.Name)
                        and test.left.id == bound
                        for test in ast.walk(child.test)
                    ):
                        return True
    return False


def check(root: Path, base: str, target: str) -> list[str]:
    if git(root, "rev-parse", "HEAD").strip() != target:
        raise RuntimeError("Candidate checkout is not the pinned target commit")
    if git(root, "merge-base", "--is-ancestor", base, target) != "":
        # exit code is the meaningful check, performed above.
        raise RuntimeError("Unexpected merge-base output")
    changed = set(git(
        root, "diff", "--name-only", "--diff-filter=ACMR",
        base, target, "--",
    ).splitlines())
    tests_changed = {p for p in changed if p.startswith("tests/")}
    template_paths = sorted((root / "app/templates").rglob("*.html"))
    all_refs = {}
    changed_templates = {}
    for template in template_paths:
        rel = template.relative_to(root).as_posix()
        now = template.read_text(encoding="utf-8")
        refs = asset_refs(now)
        for static_path, urls in refs.items():
            all_refs.setdefault(static_path, []).append((rel, urls))
        if rel in changed:
            old = git(root, "show", f"{base}:{rel}", missing_ok=True)
            changed_templates[rel] = (asset_refs(old), refs)

    errors = []
    version_changes: set[tuple[str, str]] = set()
    for path, (before, after) in changed_templates.items():
        for asset, old_urls in before.items():
            new_urls = after.get(asset, set())
            if new_urls and old_urls != new_urls:
                for old_url in old_urls - new_urls:
                    version_changes.add((path, old_url))

    # Modified static JS/CSS loaded through a template must update its URL.
    for filename in sorted(changed):
        if not (filename.startswith("app/static/") and
                filename.endswith((".js", ".css"))):
            continue
        uri = "/static/" + filename.removeprefix("app/static/")
        for template, now_urls in all_refs.get(uri, ()):
            old_content = git(root, "show", f"{base}:{template}", missing_ok=True)
            old_urls = asset_refs(old_content).get(uri, set())
            if old_urls and now_urls == old_urls:
                errors.append(
                    f"{template}: modified {filename} still uses the "
                    f"unchanged asset URL {sorted(now_urls)[0]!r}"
                )
            for old_url in old_urls - now_urls:
                version_changes.add((template, old_url))

    tests = sorted((root / "tests").rglob("test_*.py"))
    for template, old_url in sorted(version_changes):
        # Existing tests typically assert basename?v=..., not /static/....
        needle = old_url.removeprefix("/static/").split("/")[-1]
        for test_path in tests:
            rel = test_path.relative_to(root).as_posix()
            if rel in tests_changed:
                continue
            text = test_path.read_text(encoding="utf-8")
            if stale_positive_assertion(text, needle):
                errors.append(
                    f"{rel}: positive assertion still requires {needle!r}; "
                    f"version changed in {template}"
                )

    print(f"RELEASE_604_IMPACT_CHANGED_FILES={len(changed)}")
    print(f"RELEASE_604_IMPACT_CHANGED_ASSET_REFS={len(version_changes)}")
    print(f"RELEASE_604_IMPACT_UNCHANGED_TESTS_SCANNED="
          f"{len(tests) - len(tests_changed)}")
    for error in errors:
        print("RELEASE_604_IMPACT_ERROR=" + error, file=sys.stderr)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    if not SHA.fullmatch(args.base) or not SHA.fullmatch(args.target):
        parser.error("--base and --target must be exact 40-character SHAs")
    try:
        errors = check(args.root.resolve(), args.base, args.target)
    except RuntimeError as exc:
        print("RELEASE_604_IMPACT_ERROR=" + str(exc), file=sys.stderr)
        return 2
    if errors:
        print("RELEASE_604_IMPACT_PREFLIGHT=FAILED", file=sys.stderr)
        return 1
    print("RELEASE_604_IMPACT_PREFLIGHT=PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
