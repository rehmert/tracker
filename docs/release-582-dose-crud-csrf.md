# Release 582 — signed dose lifecycle strict-CSRF qualification

**Base:** Release 581, `3cffa396b00026a2c8186e86af438d7637159376`.

## Scope

Use only the disposable loopback QA server; the installed DEV/PROD
instances **remain report-only** for global strict CSRF. This release
changes no application endpoints, database schema, feature flags,
runtime middleware or deployment policy. GitHub issue #9 remains open.

New strict-only browser module `test_csrf_dose_lifecycle582.py` runs
the actual UI over HTTP and HTTPS against the two seeded synthetic
QA vials in the private database:

1. Open dose log. Submit an actual dose via HTMX; require a signed
   CSRF-header response (HTTP 200), detect the newly created row,
   and first prove an unsigned POST to `/doses` returns 403.
2. Open the new dose's native correction form, assert its hidden token,
   first reject an unsigned POST, save a modified amount and notes;
   verify a signed 303 response and the persisted exact edit value.
3. Reject an unsigned DELETE, then delete the dose via its HTMX button,
   require signed HTTP 200, disappearance of the row and HTTP 404 for
   its edit endpoint.

Tests run in isolated, ephemeral QA data only; no installed inventory
is touched. Every successful step is paired with a forged request
rejection and a valid CSRF-report header.

## Evidence and limitations

`scripts/tracker_csrf_runtime_report582.py` requires exactly two private
0600 JSON witnesses (HTTP and HTTPS), each with three route-level
positive write observations and the corresponding unsigned 403 checks.
It rejects missing, altered, extra and non-private records.
The evidence contains no cookies, tokens, actual record IDs, user
identifiers or request payloads.

After successful guarded execution, expected markers are:

```text
CSRF_582_DOSE_LIFECYCLE_EVIDENCE=VERIFIED
CSRF_582_SIGNED_WRITES=6
CSRF_582_FORGERY_REJECTIONS=6
CSRF_582_SCOPE=DOSE_CRUD_HTTP_HTTPS_ONLY
```

**Not yet proven by Release 582:** signed vial reconstitution,
filtering and preparation supply accounting, vial deletion, broader
secondary-account authorization under strict CSRF, or every JavaScript
request site. Tests and gates from Releases 579–581 remain mandatory;
a 403-only witness must never be counted as a successful signed write.

## Release process

Run guarded `tracker-release.sh` on DEV with the exact Release 581
installed base and pinned Release 582 branch commit. Require full
browser, backend and recovery qualification and preserved DEV evidence.
Then complete visual review and run dry-run `tracker_promote568.py`
preflight. **Only operator-approved** `--execute` may promote PROD.
