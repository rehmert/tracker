"""Release 705: read-only contract for the exact-commit full browser gate."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_705_full_browser_preview_is_guarded_and_noninstalling():
    source = (ROOT / "scripts/tracker-browser-preview705.sh").read_text()
    required = (
        'APP=/opt/tracker',
        'BASE=24cb9ec47417e001c3f96dfed630e3b8b0264d93',
        'REF=release/705-csrf-dependency-closeout',
        'INVOCATION_ID',
        'tracker-dev',
        'git branch --show-current',
        'git status --porcelain',
        'git rev-parse HEAD',
        'systemctl is-active --quiet tracker',
        'flock -n 9',
        'git fetch origin',
        'git merge-base --is-ancestor',
        'git diff --check',
        'git worktree add --detach',
        'bash scripts/tracker-release-scoped705.sh "$PY"',
        'git -C "$APP" worktree remove --force',
        'TRACKER_DATA_DIR="$RUN/test-data"',
        'bash scripts/tracker-browser-qualify.sh "$QA" "$PY"',
        'RELEASE_705_BROWSER_FULL=PASSED_DISPOSABLE_NO_INSTALL',
    )
    for marker in required:
        assert marker in source, marker
    assert source.index('bash scripts/tracker-release-scoped705.sh "$PY"') < source.index(
        'bash scripts/tracker-browser-qualify.sh "$QA" "$PY"'
    )
    assert source.index("RELEASE_705_SOURCE_REVALIDATED=PASSED") < source.index(
        "RELEASE_705_BROWSER_MODE=FULL_DISPOSABLE_HTTP_HTTPS_STRICT"
    )
    for forbidden in (
        'systemctl restart', 'git reset', 'git push', 'pip install',
        'pip download', 'TRACKER_CSRF_ENFORCE=1', '/etc/tracker.env',
        'tracker-release.sh',
    ):
        assert forbidden not in source, forbidden


def test_705_full_browser_preview_is_allowed_by_exact_sha_source_gate():
    preview = (ROOT / "scripts/tracker-preview705.sh").read_text()
    assert 'scripts/tracker-browser-preview705.sh|\\' in preview
    assert 'tests/test_release705_runtime_preview.py|\\' in preview
    scoped = (ROOT / "scripts/tracker-release-scoped705.sh").read_text()
    assert 'bash -n scripts/tracker-browser-preview705.sh' in scoped
    assert 'tests/test_release705_runtime_preview.py' in scoped
    assert 'tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification' in scoped
    assert scoped.index('RELEASE_705_BROWSER_RUNNER_CONTRACT=PASSED') < scoped.index(
        'RELEASE_705_ASGI_CSRF_NEGATIVE_CANARY=PASSED'
    )
