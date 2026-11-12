# Release 580 — strict-CSRF real browser lifecycle expansion

Base: Release 579, `4004fe83ac9dd39dede63cb677ea81a5d08e6b8e`.

Issue #9 stays open. **No installed DEV or PROD CSRF policy change**.
This release modifies only scripts, tests, and documentation. It neither
enables strict-CSRF on installed instances nor touches installed data in tests.

## Consolidated bundle

The existing isolated strict-CSRF Chromium gate adds
`tests/browser/test_csrf_workflows580.py` as a strict-only module. Unlike
source-only scanner results, these tests use real page controls and verify
the actual observed response method, literal runtime path, positive
CSRF-report header and success status, paired with an unsigned request
rejected with 403 before each positive step.

Each of these three workflows runs separately on HTTP and on the
host-rewriting HTTPS reverse proxy:

| Workflow | Verified write operations |
|---|---|
| Compounds | native create, rendered dynamic edit, rendered dynamic delete |
| Vitals | native create, rendered dynamic edit, HTMX DELETE |
| Notes | native create, rendered dynamic edit, native add source, native delete source, native delete page |

This bundle adds **six lifecycle scenarios** representing **22 successful
write operations with forged-denial checks**, plus **eight hostile-Origin
denial cases** on POST routes for `/compounds`, `/vitals`, `/pages` and
`/pages/preview` across both schemes. The host of these tests is always
a fresh disposable 127.0.0.1 candidate. Dynamic route IDs are never
saved to evidence receipts.

## Evidence checks

`scripts/tracker_csrf_runtime_report580.py` validates a private
closed-schema six-record report, one for each scheme and lifecycle.
Every record enumerates exact route **patterns**, methods, signed
statuses, unsigned 403 statuses, and test-only provenance. Files must
be regular 0600 private files inside the guarded browser QA workspace.
Unexpected files, fields, modified statuses or missing scenarios fail the
complete strict browser gate. The report deliberately neither includes
nor retains cookies, CSRF tokens, user data, request bodies, or dynamic IDs.

`tests/test_release580_csrf_evidence.py` checks exact operation manifests,
strict-only browser module registration, receipt tampering, unexpected
fields, missing files, world-readable files, untrusted directory and
shell syntax. The existing 579 witness suite is retained unchanged and
must also pass before the strict browser success marker.

Expected additional isolated gate lines (after actual execution):

```text
CSRF_580_LIFECYCLE_EVIDENCE=VERIFIED
CSRF_580_LIFECYCLE_SCENARIOS=6
CSRF_580_WRITE_OPERATIONS=22
CSRF_580_ROUTE_PATTERNS=11
CSRF_580_SCOPE=SELECTED_FLOWS_ONLY
```

These are **not** assertions that all unsafe routes or 46 JavaScript
callsites are compatible. The existing Release 579 two-callsite witness
count remains separate; Issue #9 also retains the live reversible DEV
strict-CSRF rehearsal and secondary-account work as future gates.

## Release discipline

Deploy the exact candidate to DEV through the installed
`scripts/tracker-release.sh` with pinned base/target/ref. Its isolated
browser gate runs first, then the complete backend tests, backup/restore
verification and installed DEV checks. The guarded script must emit
`EXIT_STATUS=0`, successful recovery verification, and automatically
preserve `/etc/tracker-release/release-580-dev.log`.

Conduct visual DEV review, then perform a non-deploying
`scripts/tracker_promote568.py` preflight. Only after explicit operator
approval is `--execute` permitted to promote exact qualified commit
through the signed DEV-controlled PROD workflow. Do not promote a failed
or incomplete release.
