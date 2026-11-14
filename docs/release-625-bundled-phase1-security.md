# Release 625 — bundled Phase 1 security qualification

Baseline: Release 624, commit `70a4805859e5139df9ed6daa83593009ef4b5944`.

## Consolidated Phase 1 objective

Instead of Releases 625–629, the remaining Phase 1 security work will
be tracked under one guarded release candidate. The bundle collects
static route/form/JS findings from Releases 620–623 and regression
evidence for URL-encoded native and multipart write semantics from
Releases 624–625.

This candidate adds strict-mode *representative* TestClient checks for:
missing and valid URL-encoded tokens; missing and valid multipart
headers; native multipart signed fields; duplicate multipart fields;
and signed-token requests with a cross-origin header.

All positive requests intentionally have invalid route payloads and must
reach route validation (422) rather than modify records. Negative
requests must receive 403. The tests run with `TRACKER_CSRF_ENFORCE=1`
only in the isolated test fixture, not in a production environment.

## Release gate and unresolved acceptance

A successful source/test deployment is **not** proof of global coverage.
Before activating strict CSRF for DEV or PROD, explicitly review the
consolidated queue, every native legacy and multipart workflow, and
every dynamic JS write call. Run isolated HTTP/HTTPS Chromium tests
with authenticated, missing, altered, replayed and cross-origin tokens
on representative real forms and uploads. Verify that successful valid
writes remain functional, including file and database behavior.
Any uncovered endpoint must be fixed and requalified on this branch.

The existing proxy-origin exceptions and mandatory session/secondary
CSRF protections remain unchanged. This candidate deliberately does
not set `TRACKER_CSRF_ENFORCE=1` on DEV or PROD. That would require
a separate **explicit operational approval after runtime evidence**,
even if all source tests pass.

## Single-release-per-phase plan

- Phase 1: Release 625 (this security qualification bundle)
- Phase 2: Release 626 (dependency reproducibility; separate approval
  for constraints, locking, CI and possible package changes)
- Phase 3: Release 627 (release failure and SSH diagnostics)
- Phase 4: Release 628 (read-only administrative visibility)

Every phase still requires a complete interactive guarded DEV
qualification and an explicit signed PROD promotion, including
nondeploying preflight and reviewed `--execute`. A phase is not
considered completed until its acceptance evidence is verified.
