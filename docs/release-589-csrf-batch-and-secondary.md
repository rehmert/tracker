# Release 589 — bundled CSRF preflight and secondary-account isolation checks

Base: combined Release 587–588 PROD commit
`c604ac79a2b084895afb1dab6a7ad6fa36b5b465`.

## Why this is a single release

The previous workflow ran a DEV source/backend preflight separately for each
browser module. Release 589 adds one **explicit, allowlisted** preflight token,
`csrf-batch589`, that executes the existing 587 bulk and 588 native multipart
Chromium tests sequentially in one disposable strict-CSRF candidate server.
The 587 private receipt verifier still runs and the entire command fails
closed if any test or evidence verifier fails.

The source/backend tests also run once instead of twice. This saves repeated
Git fetches, worktrees, pytest startup and server startup, while preserving the
normal full DEV and production promotion gates unchanged.

The batch is **not** a substitute for full DEV qualification and never
emits `ISOLATED_STRICT_CSRF_BROWSER=PASSED` or executes a deployment. It
does not silently change `TRACKER_CSRF_ENFORCE` on installed services.

## New security coverage

`tests/test_release589_secondary_strict_csrf.py` uses existing
**disposable staged-user workspaces** and independent secondary-session
CSRF tokens:

- On HTTPS, user 2's signed compound create succeeds while forged
  and cross-site POSTs are rejected before mutation.
- The same synthetic data remains unavailable to user 3 after login,
  and the separate user 3 database remains unchanged.
- An HTTP request receives a Secure secondary CSRF cookie, but it is
  **not** sent over plaintext HTTP; even the matching submitted token
  cannot authenticate an HTTP login.

These are **TestClient integration scenarios**, not real Chromium
evidence for every secondary-account flow. They do not complete the
global route inventory, javascript callsite triage, native upload matrix
or Issue #9. Readiness remains **blocked**, and global CSRF on installed
DEV and PROD remains report-only.

## Qualification and rollback

Run one pinned targeted `csrf-batch589` preflight, then run the **unchanged**
full guarded DEV release once. The normal release still verifies source,
all browser gates, all backend tests, backup/restore and smoke checks.
A dry-run production preflight and operator approval remain required
before production promotion.

If the batch or full gate fails, leave the already deployed Release 587–588
PROD baseline intact. Do not merge, force-reset or skip full qualification.
