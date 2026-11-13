# Release 592 — PK schedule, batch and import strict-CSRF compatibility

Baseline: Release 591 `cd86d7817743f3eeece9edd18a8323c47229d884`.

This release adds real signed Chromium HTTP/HTTPS compatibility and
unsigned forgery denial for **13 additional PK unsafe routes** in the
already-mandatory full strict browser module
`tests/browser/test_strict_csrf521.py`:

- Dose sequence preview, batch creation, bulk deletion, undo with audit and
  revision state;
- Staged schedule preview and revision-guarded replacement;
- Weekday calendar preview and revision-guarded replacement;
- Workspace transform preview and revision-guarded application;
- Scenario duplication with persisted dose preservation;
- Scenario template import preview and atomic import confirmation.

The tests create a synthetic supported compound and scenario inside the
existing disposable strict-CSRF browser server. Each route rejects a
tokenless request with HTTP 403, accepts a signed browser-fetch request,
reports the token valid, and validates the returned result. Positive mutation
paths additionally verify subsequent GET state: dose count, amounts, undo,
schedule replacement, transformed amounts, duplicate scenario and imported
scenario. The test cleans up its scenarios within disposable QA.

The 591 unsafe PK rejection matrix previously covered 30 single-line route
decorators. `/pk/scenarios/import-confirm` is a 31st route with a multiline
decorator, so it is now included in the unsigned matrix and the source
contract explicitly handles multiline declarations.

The 588 readiness inventory and 590 gap planner now list 20 PK source
candidates (7 from 591, 13 from this release). Assuming the unchanged
144-route inventory, they should report 39 source candidates and 105
remaining source-unqualified unsafe routes after qualification. The planner
itself does not execute runtime witnesses and still reports
`CSRF_590_GLOBAL_ENFORCEMENT=BLOCKED`.

No application router, database schema, runtime CSRF enforcement setting,
browser runner, services, or installed data are changed. Signed compatibility
is *not* claimed for the remaining PK endpoints (workbench, saved protocol
library, checked batch creation, workspace edit or historical restore).
Those require their own positive tests with valid domain fixtures and
cross-account controls before inclusion in evidence counts.

## Gate

Run changed backend source-contract tests in a disposable candidate worktree,
then one guarded **full DEV** qualification and deployment, which invokes the
already-mandatory strict Chromium module. Review DEV before conducting the
standard PROD dry-run and explicitly authorized promotion. Avoid separate
per-route targeted browser preflights. Do not turn on global CSRF enforcement.
