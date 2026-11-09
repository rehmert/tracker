# Release 521 — independently gated strict-CSRF browser qualification

Base: DEV-qualified/PROD-confirmed Release 520,
`416ff7b6be1072aded43294cf9593d3e62436703`.

## Scope

This is a qualification and test-hardening release. It does **not** enable
`TRACKER_CSRF_ENFORCE=1` on installed DEV or PROD services, change user
permissions, change DB schema, or alter the request authorization policy.
Global enforcement continues to default to report-only.

The existing release runner already creates an offline, private and
disposable candidate worktree, database, localhost HTTP server and ephemeral
HTTPS proxy. The browser gate now runs two distinct passes:

1. **Current compatibility:** full existing browser suite, served by an
   isolated `TRACKER_CSRF_ENFORCE=0` candidate.
2. **Strict security compatibility:** gracefully stop only the **isolated**
   candidate process and re-start the same candidate, loopback port and
   temporary fixture database with `TRACKER_CSRF_ENFORCE=1`. Keep the
   temporary HTTPS proxy on the same private backend. Before running tests,
   require an unauthenticated JSON write lacking a CSRF token to be denied
   with 403 by the strict middleware.

The strict pass runs `tests/browser/test_strict_csrf521.py`, the
previously qualified real native HTTPS Labs upload suite (Release 501),
and the existing Food/Labs browser mutation suite (Release 500).

## New strict Chromium matrix

- Native URL-encoded compound creation, signed hidden field and forged POST
  denial without a database write.
- Native HTTPS COA multipart PDF upload and signed metadata update; forged
  COA upload denied.
- Existing native HTTPS Labs multipart document create/edit/delete plus
  report-only baseline tests.
- Real same-origin `window.fetch()` POST with injected
  `X-Tracker-CSRF` header; a headerless JSON POST is denied.
- Real HTMX live page Markdown preview and HTMX DELETE of a disposable
  vital; both require signed submission and return valid status.
- Existing browser Food mutations and Labs lifecycle flows under strict
  mode (not just HTTP TestClient requests).

Two new standalone temporary-database tests also exercise the **actual**
root middleware and route definitions under strict mode for administrator
login, signed account-security session-revocation, logout, private secondary
sign-in, private security session-revocation, and secondary logout. They
instantiate disposable accounts and do not touch live authentication stores.

All strict-browser writes target `/tmp/tracker-browser-qa.*/data`, with
unique private ephemeral HTTP/HTTPS ports. The test module refuses to collect
against anything except a validated loopback temporary candidate; no remote
URLs or production service credentials are permitted. The browser runner
kills and waits for candidate subprocesses before exiting.

## Operational limits

Passing Release 521's browser gate shows **the exercised workflows** work
in the strict test harness. It is not proof that every legacy form,
third-party client, oversized URL-encoded form, or streaming API workflow
works under global enforcement. Do not change `/etc/tracker.env`, the
production systemd environment, or `TRACKER_CSRF_ENFORCE` after installing
this release solely because the suite passes.

Next, review the reported CSRF readiness inventory for remaining
uninspected and legacy submission paths. A separate explicit PROD policy
change requires documented coverage for *all* production writes, including
large forms, after operator approval.

## DEV release acceptance

GitHub is **source control only**, never CI. Run the pinned candidate through
`scripts/tracker-release.sh --instance DEV` and require:

- `ISOLATED_BROWSER=PASSED` and `ISOLATED_STRICT_CSRF_BROWSER=PASSED`;
- complete backend regression including signed login/account tests;
- restored source + SQLite + uploads using the existing isolated drill;
- DEV health/sidebar runtime smoke and `EXIT_STATUS=0`.

If any strict-mode browser case fails, the release worker must stop before
source installation and keep installed DEV/PROD services unaffected.

No schema, dependency, model, reverse-proxy, or installed service changes.
