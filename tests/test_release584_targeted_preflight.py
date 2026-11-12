"""Release 584: targeted QA remains DEV-only, isolated and non-deploying."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "scripts/tracker-targeted-preflight584.sh"
BROWSER = ROOT / "scripts/tracker-browser-qualify.sh"
RELEASE = ROOT / "scripts/tracker-release.sh"


def test_584_shell_scripts_parse_and_fail_closed_for_invalid_args():
    for file in (PREFLIGHT, BROWSER):
        check = subprocess.run(["bash", "-n", str(file)],
                               text=True, capture_output=True)
        assert check.returncode == 0, (file, check.stderr)
    failure = subprocess.run(["bash", str(PREFLIGHT), "--bogus", "value"],
                             text=True, capture_output=True)
    assert failure.returncode == 2
    assert "Usage:" in failure.stderr


def test_584_source_pinning_and_no_deployment_actions():
    source = PREFLIGHT.read_text(encoding="utf-8")
    for needle in (
        'labels != ["DEV"]', 'tracker-preflight-584.',
        'rev-parse HEAD', 'rev-parse "refs/remotes/origin/$REF"',
        'merge-base --is-ancestor "$BASE" "$TARGET"',
        'git -C "$APP" worktree add --detach "$WORK" "$TARGET"',
        'git -C "$APP" worktree remove --force "$WORK"',
        'TRACKER_DATA_DIR="$BACKEND_DATA"',
        'timeout 180', 'timeout 240',
        'TARGETED_PREFLIGHT=PASSED',
        'TARGETED_SCOPE=SOURCE_AND_RELEASE_583_ONLY_NOT_FULL_QUALIFICATION',
    ):
        assert needle in source, needle
    assert 'git -C "$APP" merge --ff-only' not in source
    assert 'git -C "$APP" reset --hard' not in source
    assert "systemctl restart tracker" not in source
    assert "tracker_promote568.py" not in source
    assert "ISOLATED_STRICT_CSRF_BROWSER=PASSED" not in source


def test_584_targeted_qualification_is_strict_only_and_cannot_forge_full_pass():
    source = BROWSER.read_text(encoding="utf-8")
    # The 587–588 isolated bulk/multipart gate adds a fourth full-mode
    # section. Guard the mode boundaries and the full success marker
    # instead of pinning this contract to the old three-section count.
    assert source.count('if [[ "$MODE" == full ]]; then') == 4
    assert source.count('ISOLATED_STRICT_CSRF_BROWSER=PASSED') == 1
    assert source.index('tests/browser/test_csrf_bulk587.py') < source.index(
        'ISOLATED_STRICT_CSRF_BROWSER=PASSED')
    assert '[[ "$MODE" == targeted ]]' in source
    assert 'TARGETED_STRICT_PREFLIGHT=ACTIVE' in source
    assert 'TARGETED_STRICT_PREFLIGHT=PASSED' in source
    assert "TARGETED_STRICT_SCOPE=RELEASE_583_ONLY_NOT_FULL_QUALIFICATION" in source
    assert "ISOLATED_STRICT_CSRF_BROWSER=PASSED" in source
    assert source.index("ISOLATED_STRICT_CSRF_BROWSER=PASSED") < source.index(
        "TARGETED_STRICT_PREFLIGHT=PASSED")
    assert '[[ "$TARGETED_MODULE" =~ ^tests/browser/test_(csrf_preparations583|form_overlap586|csrf_bulk587|csrf_multipart588)[.]py$ ]]' in source
    assert 'TARGETED_MODULE="$4"' in source
    assert 'TRACKER_CSRF_ENFORCE=1' in source
    standard, strict = source.split(
        "# Release 521: a second browser gate", 1)
    assert "test_csrf_preparations583.py" not in standard
    assert strict.count("tests/browser/test_csrf_preparations583.py") == 1
    assert strict.index("tracker_csrf_fixture583.py\" seed") < strict.index(
        "tests/browser/test_csrf_preparations583.py"
    ) < strict.index("tracker_csrf_runtime_report583.py") < strict.index(
        "tracker_csrf_fixture583.py\" verify"
    )


def test_584_full_release_still_mandates_browser_and_backend_gates():
    source = RELEASE.read_text(encoding="utf-8")
    assert 'timeout 600 bash "$QA/scripts/tracker-browser-qualify.sh" "$QA" "$PY"' in source
    assert "=== COMPLETE REGRESSION SUITE ===" in source
    assert '=== ALL BACKEND TESTS PASSED ===' in source
    assert "=== Verified source and data recovery backup ===" in source
    assert "=== Install via fast-forward ===" in source
