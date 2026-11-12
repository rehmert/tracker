# Combined Release 587–588 — strict-CSRF compatibility expansion and readiness gate

**Base:** deployed Release 586 PROD/main commit
`58554bca2ef577f570a646c344fe920ca2800692`.

## Deployment posture

This is **one combined source candidate and one guarded promotion**, not two
separately deployed releases. No changes to global installed strict-CSRF mode,
session auth, user-account flags, database schema, runtime secrets, or existing
DEV/PROD data. `TRACKER_CSRF_ENFORCE` remains **report-only** by default.
GitHub Issue #9 remains open. Do not treat this release as authorization
to enable strict CSRF on installed DEV or PROD.

## Additional strict-CSRF execution evidence

New disposable, 127.0.0.1-only Chromium tests:

1. **Release 587 bulk vial operations**: browser-originated signed
   `fetch(FormData)` requests for selection validation, update preview,
   committed bulk edit, deletion preview, and committed bulk deletion.
   The test also exercises unsigned denials for all five routes,
   independently confirms the saved edit and the deleted vial, and
   uses a freshly created disposable QA vial. Separate HTTP and HTTPS
   flows run against the same strict QA candidate. These tests do NOT
   prove a click through every advanced native bulk UI control.
2. **Release 588 native multipart COA**: a real browser `multipart/form-data`
   upload containing a synthetic PDF via the native COA form, with
   HTTP and HTTPS signed success, unsigned-request 403 rejection,
   and confirmation that the unsigned upload did not create a record.
   Existing Labs multipart checks remain mandatory.
3. **Evidence integrity**: two private 0600, root-owned bulk execution
   receipts are verified by `scripts/tracker_csrf_runtime_report587.py`.
   Wrong/missing/extra receipts, tampered operation matrices, incorrect
   schemes, and missing written/deleted verification fail the guarded run.
4. **Targeted preflight**: new browser modules are in the exact audited
   CLI allowlist, and the full guarded release still runs all prior
   Chromium gates, backend regression, restore validation and smoke checks.

Only the above test paths gain new executable evidence. There is
**no synthetic claim of blanket CSRF compatibility**.

## Source inventory and decision

Run `python scripts/tracker_csrf_readiness588.py` to generate an
explicit conservative per-route source-ledger gap report. It includes
the declared candidate witness set, routes still unqualified, unresolved
JS requests and implicit/dynamic form review queue. This source report
cannot itself establish runtime coverage. The report intentionally
returns `BLOCKED_INCOMPLETE_RUNTIME_CLEARANCE` even after this release's
isolated tests pass, because Issue #9 is not yet fully closed.

Remaining gate requirements include:

- Enumerate and execute every remaining native/multipart and unsafe route,
  including dynamic and indirect request shapes
- Independently verify secondary-account session/CSRF behavior and
  cross-account write isolation over disposable HTTP **and** HTTPS
- Capture forged/cross-site negatives and signed positives for each new
  route, preserving independent account and inventory reconciliations
- Explicitly authorize and qualify a separate DEV strict-mode rollout
  before any production enforcement change

## Operator safety and rollback decision

The deployable changes here are tests, source-audit tooling, runner
allowlists and documentation. They do not alter application routes or
the installed strict-CSRF default. The normal guarded release runner
still takes a verifiable recovery archive and tests restore prior to
installation. If DEV qualification or visual review fails, **do not
promote**: leave PROD at its known baseline and correct the candidate.
If an approved release unexpectedly affects installed behavior, use
the existing **operator-controlled verified recovery process** and
production backup; never automatically reset a database or force a
rollback from these scripts.

**Current strict-mode rollout decision: BLOCKED.** Both DEV and PROD
continue with report-only global CSRF. The evidence supports only the
new bulk and native-COA test scenarios, not complete closure of Issue #9.
