# Release 581 — inventory and dose strict-CSRF witnesses

Base / installed PROD after Release 580:
`9c403a56eb1a5350207a2a7951446d18bc2e655d`.

**No application runtime behavior, route handlers, or security configuration
is changed. Installed DEV and PROD stay report-only for global strict CSRF.**
Issue #9 remains open.

## Bundled executable coverage

This release adds `tests/browser/test_csrf_inventory581.py` to the
isolated strict-only Chromium gate. As with prior browser security tests,
it refuses to collect unless running inside a disposable 127.0.0.1
candidate with isolated QA data and strict CSRF enabled. It does not
connect to or mutate the installed DEV or PROD application.

Each of the following is executed on HTTP and HTTPS:

- **Native vial edit**: load the seeded synthetic vial, verify the actual
  CSRF hidden form field, forge an unsigned POST and require 403, then
  submit a native form using the normal browser UI; require a signed
  303, valid CSRF-report header and persisted QA note. Contents and
  inventory quantity are intentionally unchanged.
- **HTMX dose preview**: load the actual dose entry screen, change the
  visible amount field to trigger its own HTMX POST, confirm signed
  200 and transmitted CSRF header, and verify a separate unsigned
  POST is rejected with 403.
- **Six forged-only endpoint checks**: unsigned vial delete,
  reconstitution, filtering, dose create, dose delete, and dose
  preview must all fail closed with 403. These are **negative-only**
  witnesses; no legitimate positive-write compatibility is claimed
  for these endpoints.

That yields **16 browser cases** across both protocols: four signed
positive-with-rejection tests and 12 negative-only route tests.
The tests deliberately use fixed QA fixture vial IDs, not live inventory.

## Evidence contract

The browser module writes 16 private 0600 records containing only
test names, static route-pattern metadata, HTTP method, verified status
and scope flags. No token, cookie, request payload, actual identifier,
or account data is saved. The isolated runner invokes
`scripts/tracker_csrf_runtime_report581.py` and aborts unless the
closed set of records and exact expected fields/status values match.

`tests/test_release581_csrf_evidence.py` covers strict-only gate
registration, tampering, extra fields, missing files, insecure file
permissions, unsafe path aliases and runner shell syntax.

Expected markers **only after successful guarded DEV execution**:

```text
CSRF_581_INVENTORY_DOSE_EVIDENCE=VERIFIED
CSRF_581_BROWSER_CASES=16
CSRF_581_SIGNED_POSITIVE_CASES=4
CSRF_581_NEGATIVE_ONLY_CASES=12
CSRF_581_SCOPE=SELECTED_ROUTES_NOT_ALL_JS_CALLSITES
```

The previous Release 579 and 580 evidence and browser modules remain
mandatory. These selected workflows must not be taken as strict-CSRF
clearance for every route or for the 46-tracked-JavaScript-callsite
inventory. The separate secondary-account compatibility and broader
production rollout decisions remain future work.

## Qualification and promotion

Run the existing guarded `tracker-release.sh` on DEV with the pinned
Release 580 base, exact Release 581 target SHA, and this release branch.
It must finish with successful isolated browser, full backend tests,
backup/restore, and automatically persisted qualification evidence.

Then perform visual DEV review and a non-deploying
`tracker_promote568.py` preflight. Only after the operator explicitly
approves, rerun promotion with `--execute`. Do not change installed
strict-CSRF enforcement by promoting this release.
