# Release 577 — DEV qualification evidence and strict-CSRF regression bundle

Base: Release 576 `3414f736fc19b09b8647f61b8c90577046a1f4f3`.
Issue #9 remains open. This is a candidate, **not** a live global
strict-CSRF rollout. Neither installed environment changes its
`TRACKER_CSRF_ENFORCE` configuration.

## Scope

1. Automatically preserve the exact DEV deployment evidence in a
   root-only `/etc/tracker-release/release-<N>-dev.log` after the
   guarded worker reaches success. The helper checks the candidate
   SHA, strict/regular browser outcomes, backend and restore markers,
   final successful status, and the guarded success heading. It
   rejects symlinks, unsafe source paths/permissions and existing
   receipts (never overwriting a prior approval artifact). The
   original log remains available under its existing private
   `/tmp/tracker-backups/release.*/` workspace.
2. Treat failed receipt persistence as a deployment failure. The
   original code-only rollback remains in place. PROD never creates
   a DEV qualification receipt.
3. Regress the receipt parser against incomplete, contradictory,
   mismatched-SHA and forged qualification evidence. Shell syntax
   and the existing signed promotion ordering remain under tests.
4. Expand the disposable strict Chromium matrix across local HTTP
   and host-rewriting HTTPS with cross-site requests that deliberately
   include an otherwise valid signed token. Verify that hostile
   Origin/Fetch Metadata still deny JSON, multipart and larger
   JSON bodies, and that unsigned large same-origin requests fail.
5. Extend the existing secondary-session TestClient fixture with
   signed positive revoke, missing/forged token rejection, cross-site
   denial and cross-user session isolation under a temporary strict
   environment flag. These secondary tests do not themselves
   establish a live reverse-proxy secondary-account rollout.

## Required review

- The guarded DEV worker must show
  `DEV_QUALIFICATION_EVIDENCE_PRESERVED=` with a protected receipt
  and `EXIT_STATUS=0` only after all qualification gates.
- The separate `tracker_promote568.py` default preflight must still
  independently validate the persisted receipt and exact commit.
- Do not run `--execute` or promote PROD before reviewing DEV tests,
  release logs, and human browser acceptance.
- The 46 JS callsites remain a source-only queue, not 46 individually
  executed writes. Route-by-route clearance, secondary mounted live
  strict enforcement, unexpected body encodings and strict-CSRF
  configuration rehearsal are not complete. Issue #9 remains open.
- A live DEV-only strict rehearsal and any PROD strict flag change
  require separately approved reversible procedures.

## Test and deployment procedure

Focused candidate regressions (run in the isolated candidate checkout,
not by changing an installed checkout):

```bash
.venv/bin/python -m pytest -q \
  tests/test_release577_dev_receipt.py \
  tests/test_secondary_sessions441.py
```

The existing guarded DEV release runner executes its full backend,
isolated Chromium HTTP/HTTPS, strict-CSRF, recovery and normal
post-install verification gates. New browser cases are in
`tests/browser/test_strict_csrf521.py` and are automatically collected
by the existing browser gate.

The branch remains source/test/tooling/docs-only: no application
restart, schema migration, dependency changes, GitHub Actions
deployment or off-host backup copying is introduced.
