"""Release 708: exact historical route inventory and strict-browser wiring.

Source-only. Actual 19-route qualification requires detached Chromium on
disposable DEV and a successful tracked systemd receipt.
"""
from __future__ import annotations

import ast
from pathlib import Path

from scripts.tracker_csrf_reconcile627 import (
    build, POST_654_PLUS_UNQUALIFIED_ROUTES,
)

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "tests/browser/test_csrf_remaining_workout708.py"
WORKOUT707 = ROOT / "tests/browser/test_csrf_workout_lifecycles707.py"
RUNNER = ROOT / "scripts/tracker-browser-qualify.sh"
INVENTORY = ROOT / "tests/test_browser_qualification511.py"
WORKER = ROOT / "scripts/tracker-csrf-positive708.sh"


def routes_from_ast(source: Path, name: str) -> set[tuple[str, str]]:
    tree = ast.parse(source.read_text(encoding="utf-8"))
    matches = [
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == name
    ]
    assert len(matches) == 1
    value = matches[0].value
    assert isinstance(value, ast.Call)
    assert isinstance(value.func, ast.Name)
    assert value.func.id == "frozenset"
    assert len(value.args) == 1
    return set(ast.literal_eval(value.args[0]))


def test_708_all_nineteen_remaining_workout_routes_exact_historical_set():
    report = build()
    covered = routes_from_ast(WORKOUT707, "WORKOUT_ROUTES")
    present = routes_from_ast(CURRENT, "ROUTES")
    all_workout = {
        key for key in POST_654_PLUS_UNQUALIFIED_ROUTES
        if key[1].startswith("/workouts/")
    }
    assert len(all_workout) == 36
    assert len(covered) == 17
    assert len(present) == 19
    assert not covered & present
    assert covered | present == all_workout
    pending = {(entry["method"], entry["path"])
               for entry in report["remaining_routes"]}
    assert present <= pending
    # Historical source-only 705 report has not magically reconciled new
    # runtime evidence: keep explicit operator receipt separate.
    assert report["remaining_without_positive_source_witness"] == 92
    assert report["global_enforcement_authorized"] is False


def test_708_nineteen_forgery_and_persistence_checks_wired_in_browser():
    source = CURRENT.read_text(encoding="utf-8")
    for needle in (
        'TRACKER_TEST_ISOLATED") == "1"',
        'TRACKER_TEST_STRICT_CSRF") == "1"',
        'DATA.parent.parent == Path("/tmp").resolve()',
        'window.trackerCsrfToken?.()',
        'cookie["value"] == token',
        'missing.status == 403',
        'forged.status == 403',
        'assert before() == original',
        'accepted.headers.get("x-tracker-csrf-report") == "valid"',
        'assert seen == ROUTES',
        'scenario(browser, HTTP_URL, "http")',
        'scenario(browser, HTTPS_URL, "https")',
        'workout_routine_group_members668',
        'workout_routine_targets667',
        'workout_set_corrections668',
        'workout_sessions654',
        'date(started_at)',
        '"/workouts/backfill/import.csv"',
        '"/workouts/finish-review"',
        '"/workouts/sets/repeat"',
    ):
        assert needle in source, needle
    for unsafe in (
        '/opt/tracker/data/tracker.db', 'DROP TABLE',
        'TRACKER_CSRF_ENFORCE=0', 'os.system(',
        'subprocess.run(', 'curl ', 'requests.post(',
    ):
        assert unsafe not in source
    assert source.count('seen.add(("POST", ') == 18


def test_708_full_strict_gate_registers_once_and_targeted_mode_does_not_repeat():
    runner = RUNNER.read_text(encoding="utf-8")
    module = "tests/browser/test_csrf_remaining_workout708.py"
    assert runner.count(module) == 2
    start = runner.index('echo "=== STRICT CSRF CORE TESTS PASSED ==="')
    targeted = runner.index(
        'if [[ "$MODE" == targeted && "$TARGETED_MODULE" == csrf-positive708 ]]'
    )
    assert runner[start:targeted].count(module) == 1
    assert "STRICT_CSRF_708_WORKOUT_19_POSITIVE_LIFECYCLES=PASSED" in runner
    assert "TARGETED_CSRF_708_WORKOUT_19_SIGNED_LIFECYCLES=PASSED" in runner
    assert "TARGETED_CSRF_708_SCOPE=19_REAL_WRITES_NOT_FULL_CSRF_CLEARANCE" in runner
    index = INVENTORY.read_text(encoding="utf-8")
    assert '"tests/browser/test_csrf_remaining_workout708.py"' in index
    assert '("csrf-positive708", "TARGETED_CSRF_708_WORKOUT_19_SIGNED_LIFECYCLES=PASSED")' in index


def test_708_dev_only_exact_ref_no_install_no_main_promotion():
    shell = WORKER.read_text(encoding="utf-8")
    for marker in (
        "BASE=4c084ade9063b3b01c2de0a4a055d2e23470b2a3",
        "REF=release/708-csrf-remaining-workout-positives",
        'git merge-base --is-ancestor "$BASE" "$TARGET"',
        'git worktree add --detach "$QA" "$TARGET"',
        'git -C "$APP" worktree remove --force "$QA"',
        "tests/test_release707_csrf_positive.py",
        "tests/test_release708_csrf_remaining.py",
        "--targeted-strict csrf-positive708",
        "RELEASE_708_TARGETED_WORKOUT_19=PASSED_NOT_GLOBAL_CLEARANCE",
        "RELEASE_708_SOURCE=PASSED",
        'readlink /proc/self/ns/net',
        'readlink /proc/1/ns/net',
    ):
        assert marker in shell, marker
    for forbidden in (
        'git push', 'systemctl restart tracker', '/etc/tracker.env',
        'pip install', 'pip download', 'ssh ',
    ):
        assert forbidden not in shell
