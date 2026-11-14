# Release 627 — Consolidated strict-CSRF gap evidence (not activation)

Baseline: production Release 626 at
`b6402508ba489ee044ec718d027ebd006655b601`.

## Why this release is bundled

The existing Release 590 gap report reports 144 unsafe route declarations,
83 candidates for isolated Chromium browser evidence, 61 routes still
lacking a mapped positive signed browser witness, and 110 manual-review
items. All remain conservative source-review categories, not proof of
application vulnerabilities.

Instead of one release for each route or workstream, Release 627 adds a
single strict-mode negative test matrix and a representative HTTP/HTTPS
Chromium gap gate to the established full qualification path. Nothing
changes the installed application security policy or dependency versions.

## What tests do

- **55 ordinary write routes** are exercised twice in the isolated strict
  TestClient: a tokenless URL-encoded request and one with a tampered CSRF
  request header. Both must be denied by middleware (403) before mutations.
- **Six session-owned routes** are intentionally excluded from the global
  matrix: `/login`, `/logout`, `/account/password`,
  `/account/sessions/revoke-others`, `/account/users` and
  `/account/users/edit`. Those require independent signed session-token
  and account-identity acceptance; a disabled-auth fixture cannot prove it.
- **15 representative workstream routes** are tested via Chromium against
  isolated HTTP and HTTPS (30 contexts), with cookies established by an
  HTML GET. The browser API deliberately bypasses the app's JavaScript CSRF
  wrapper, and unsigned/forged writes must fail closed. No real data is used.
- A new fail-closed source assertion verifies that the Release 590 gap set
  still has the expected 61 routes; changes to that set must be explicitly
  reviewed rather than silently marked protected.

This is **negative coverage only**. A request can be correctly denied
while the corresponding legitimate signed user workflow remains broken.
No route is added to the 590 candidate manifest merely due to a 403 test.
The 61 unqualified count remains the correct conservative count until
positive signed lifecycle/response/mutation evidence is linked.

## Unfinished acceptance and issue #9

1. Implement and qualify positive signed browser lifecycles, paired with
   rejection of forged requests, across the remaining ordinary write routes.
2. Complete independent session-owned identity, authentication and secondary
   cross-account browser checks under HTTP/HTTPS reverse proxy behavior.
3. Reconcile 110 manual-review records, including dynamic JS and implicit
   forms. Assign either explicit runtime evidence or documented exclusions
   with reasons; do not silently infer from source matches.
4. Run the full, one-time guarded DEV qualification for this consolidated
   candidate, and review any browser failures before promotion.
5. Only after all gaps close and the operator approves a separate guarded
   change may strict mode be activated on installed DEV, then PROD, with
   rollback and observation. This release DOES NOT turn it on.

## Dependency reproducibility, issue #10

A fresh virtual environment on tracker-dev successfully installed the
43 informational pins plus pip 25.1.1; the exact 44-package baseline matched,
`pip check` passed and 11 focused tests passed. This is useful new
evidence, but it reused the host OS and pip cache; it does not prove
host-independent reproduction, wheel artifact hashes, the Playwright Chromium
binary/system-library set, or full disposable backend/browser QA.
No new package installation or requirement edits are part of Release 627.

## Qualification

Use the standard original interactive DEV guarded release process for the
single complete candidate, including focused tests, full 16-worker backend
suite, HTTP/HTTPS Chromium, immutable receipts, and explicit signed PROD
promotion after preflight and visual approval. The previous 626 deployment
is the exact base for both environments. No PROD changes are authorized
solely by passing these negative tests.

## New positive browser lifecycle evidence (same candidate)

The full guarded browser gate now also schedules
`tests/browser/test_csrf_signed_lifecycles627.py`: six independent
HTTP/HTTPS Chromium cases. Each creates its own synthetic protocol,
page or lab report through a **real native signed HTML form** and
requires a 303 redirect and persisted record. The same browser context
then sends a properly signed application edit/state-change request,
verifies persisted changes, and deletes that synthetic record, with
unsigned forged update and deletion attempts rejected (403).
Tests never operate on existing user data.

These cases provide real positive lifecycle evidence for a subset of
previously unqualified routes:

- `POST /protocols`, `POST /protocols/{pid}/active`,
  `POST /protocols/{pid}/delete`
- `POST /pages`, `POST /pages/{pid}`,
  `POST /pages/{pid}/delete`
- `POST /labs`, `POST /labs/{rid}/results`,
  `POST /labs/{rid}/delete`

Edit/delete requests are signed through Chromium's isolated request
context, not native button clicks. These declarations have NOT been
automatically added to the historical 590 manifest. Runtime execution
must pass and its evidence must be reviewed before qualifying any route.
Additional purchase, blend, COA and other high-priority workstreams,
plus the 110 manual-review records, are still outstanding; do not
enable global enforcement based on these subset tests.
