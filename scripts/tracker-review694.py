#!/usr/bin/env python3
"""Release 694: fail-closed review for the navigation and daily shortcut change."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

BASE = "4d752be1a62ffa8a5feba78a50033e980a30b26c"
EXPECTED = frozenset({
    "app/static/tracker_focus.js",
    "app/static/tracker_focus.css",
    "app/templates/base.html",
    "app/templates/dashboard.html",
    "app/templates/mobile_today509.html",
    "app/templates/_daily_actions694.html",
    "app/static/css/tracker-daily-shortcuts694.css",
    "tests/test_dashboard_polish688.py",
    "tests/test_release559_everyday_bundle.py",
    "tests/test_everyday_navigation694.py",
    "scripts/tracker-review694.py",
    "scripts/tracker-release-scoped694.sh",
    "scripts/tracker-preview694.sh",
})


def git(root: Path, *args: str) -> str:
    return subprocess.check_output([
        "git", "-c", f"safe.directory={root}", "-C", str(root), *args
    ], text=True)


def review(root: Path, base: str, target: str) -> None:
    if base != BASE or git(root, "rev-parse", "HEAD").strip() != target:
        raise ValueError("Incorrect Release 694 baseline or candidate")
    subprocess.run([
        "git", "-c", f"safe.directory={root}", "-C", str(root),
        "merge-base", "--is-ancestor", base, target
    ], check=True)
    changed = frozenset(git(root, "diff", "--name-only", base, target).splitlines())
    if changed != EXPECTED:
        raise ValueError("Unreviewed file changes: " + repr(sorted(changed ^ EXPECTED)))
    if git(root, "diff", "--name-only", "--diff-filter=D", base, target).strip():
        raise ValueError("Unexpected deleted source files")
    if any(name.startswith(("app/routers/", "app/models", "app/db", "app/migrations"))
           for name in changed):
        raise ValueError("Release 694 must not change backend or database code")
    base_html = (root / "app/templates/base.html").read_text(encoding="utf-8")
    focus = (root / "app/static/tracker_focus.js").read_text(encoding="utf-8")
    focus_css = (root / "app/static/tracker_focus.css").read_text(encoding="utf-8")
    actions = (root / "app/templates/_daily_actions694.html").read_text(encoding="utf-8")
    dash = (root / "app/templates/dashboard.html").read_text(encoding="utf-8")
    today = (root / "app/templates/mobile_today509.html").read_text(encoding="utf-8")

    for required in (
        'id="tracker-focus-sidebar-toggle"',
        'id="nav-sortable"',
        'id="tracker-focus-toggle"',
        '/static/tracker_focus.js?v=694',
        '/static/tracker_focus.css?v=694',
        'id="nav-filter"',
        'id="command-open"',
        'id="tracker-mobile-more"',
        'id="nav-favorites"',
    ):
        if required not in base_html:
            raise ValueError("Critical sidebar/search/favorites contract lost: " + required)
    if "let enabled = true" not in focus or "saved !== null" not in focus:
        raise ValueError("Default or saved preference behavior changed unexpectedly")
    for critical in (
        "'/mobile'", "'/workouts'", "'/food'", "'/regimen'",
        "'/doses'", "'/vials'", "'/labs'", "'/pk'", "'/protocols'",
        "active.has(href)", "localStorage.setItem(KEY",
        "'tracker-focus-sidebar-toggle'",
    ):
        if critical not in focus:
            raise ValueError("Everyday/active link or persistence lost: " + critical)
    if "min-height: 44px" not in focus_css:
        raise ValueError("Sidebar control touch target too small")
    for href in (
        "/mobile", "/doses#quick-dose-entry", "/food#food-quick-log",
        "/mobile#mobile-quick-vitals", "/workouts/quick",
        "/vials", "/quick-entry",
    ):
        if f'href="{href}"' not in actions:
            raise ValueError("Canonical daily action lost: " + href)
    for page, source in (("dashboard", dash), ("today", today)):
        if '{% from "_daily_actions694.html" import daily_actions694 %}' not in source:
            raise ValueError("Daily macro not imported on " + page)
        if "{{ daily_actions694() }}" not in source:
            raise ValueError("Daily macro not used on " + page)
        if "/static/css/tracker-daily-shortcuts694.css?v=694" not in source:
            raise ValueError("Daily styles not pinned on " + page)
        if 'class="tracker-daily-extra694"' not in source:
            raise ValueError("Secondary actions were removed on " + page)
    if "/regimen#reg635-today" not in today or "/food#food-water" not in today:
        raise ValueError("Today supplement or water route lost")
    for href in ("/calendar", "/dose-workspace", "/replenishment-review",
                 "/labs", "/health-insights", "/food#food-water"):
        if f'href="{href}"' not in dash:
            raise ValueError("Overview advanced shortcut was removed: " + href)
    print("RELEASE_694_NAVIGATION_SOURCE_REVIEW=PASSED")
    print("RELEASE_694_ALL_EXISTING_ROUTES=PRESERVED")
    print("RELEASE_694_DB_SCHEMA_CHANGE=NONE")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    a = parser.parse_args()
    review(a.root.resolve(), a.base, a.target)


if __name__ == "__main__":
    main()
