# Release 511: test safety, audit accuracy, and small correctness fixes

## Scope

This candidate is based on Release 510 commit
`2de6ebd3f37c90f9e7cdb56dedc7eeab9b86e138`.
It is **not a completed release** until DEV's isolated browser and complete
backend test gates pass and the installed runtime is checked. No PROD deploy
is authorized by this document.

## Test invocation

- `bash scripts/tracker-test.sh --quick`: focused backend checks.
- `bash scripts/tracker-test.sh --full`: non-browser backend tests;
  `TRACKER_TEST_PYTHON` can point at a different virtual environment.
- `bash tracker-test.sh quick|full`: compatibility aliases.
- `bash tracker-test.sh browser`, `bash run_browser_tests.sh`,
  or `bash scripts/tracker-test-gate475.sh browser`: require
  `TRACKER_BROWSER_CANDIDATE` set to an **independent detached worktree**.
  They refuse to test the installed application.
- `bash tracker-test.sh all|release`: refuses to claim comprehensive
  qualification unless a separate candidate worktree is configured.
- `bash scripts/tracker-release.sh --instance DEV ...`: the normal
  *guarded deployment* path, including isolated browser QA and backend
  tests before any installation.

Never point browser mutation tests at `127.0.0.1:8000` on an installed
DEV or PROD host. Do not disable the browser module's collection guards.

### Browser coverage

The candidate's `scripts/tracker-browser-qualify.sh` runs all twelve
`tests/browser/test_*.py` modules and seven isolated browser fixture modules
from `tests/` against either self-contained HTML or a disposable candidate
service on random loopback HTTP/HTTPS ports. The runner never reads the
installed database or any live credentials. Existing live sorting tests can
skip data-dependent assertions when the disposable inventory is empty;
isolated fixture tests provide deterministic coverage of sorting logic.

The former 300-second browser-stage timeout is 600 seconds to accommodate
the additional Playwright tests. A failed browser gate stops deployment.

## Source corrections

1. Record Explorer's direct SQLite connections now use `closing()`, rather
   than relying on sqlite3's transaction context manager to close them.
2. An empty or whitespace-only server-managed theme override falls back
   to the checked-in default CSS.
3. Food Journal refuses the two extreme representable calendar dates,
   avoiding predecessor/successor overflow.
4. The expanded verification script uses fresh per-run report files and
   fails instead of claiming success for missing, corrupt, or failing
   source audit reports.
5. Host security diagnostic wording acknowledges that incomplete Basic Auth
   configuration fails closed with HTTP 503.
6. A regression test explicitly checks that the CSS endpoint requires valid
   Basic Auth when that authentication mode is enabled.

## Security considerations and limits

General legacy CSRF enforcement is still opt-in. Origin/Fetch Metadata
protection and form-specific CSRF checks remain unchanged. Do **not**
silently set `TRACKER_CSRF_ENFORCE=1`: multipart and legacy flows require
end-to-end compatibility testing before that can be a safe default.

The installed Python dependencies are version-ranged rather than locked.
Capture a tested environment snapshot and evaluate compatibility before
introducing a lockfile. A GitHub test runner cannot replace a guarded
restore/recovery drill on the actual DEV host.

## Acceptance

- Review the PR diff and verify no protected route is made anonymous.
- Execute the full isolated DEV browser gate, including negative cross-site
  and HTTPS native Lab mutation tests.
- Execute the complete non-browser test suite.
- Run source quality checks and an authenticated live smoke.
- Verify the exact target SHA, backup restore and code-only rollback gates
  via the existing pinned release workflow.
- Promote to main and PROD **only after** DEV qualification and review.
