# Release 746 — One integrated remaining-backlog hardening release

Baseline: DEV+PROD 745 at b7435e55659fbb09819101ebd621aca2c72059c9. Ref release/746-final-hardening-macd-css.

## Mobile / CSS #54
Five consecutive global stylesheets 685–689 load as a single original-order,
verbatim concatenation with a cache-busted URL. Existing stylesheets remain
unchanged as historical sources. Four fewer CSS requests per page. Chromium
parity at 320, 390, 430, 760 and 1024 pixels, dark/light and all three
density settings is qualified together with historical CSS browser tests.

## MACD #56
Cross-module action forms and unsafe route declarations are checked in new
tests for Regimen, Workouts, Food, Supplies, COAs, Labs and Notes; older
owner-scoped API/DB tests remain in qualification. Actual corrections,
conditional Move and guarded Delete continue to preserve history.
The earlier Release 745 Water day/amount correction is regression-tested.
Full real-phone/owner-by-owner interactive acceptance is not claimed.

## Security #9
Isolated HTTP and HTTPS TestClient exercises signed Water native Add/Edit,
missing and forged token negatives under strict opt-in, plus historical
multipart strict regression and current unsafe-route scanner. This is only
incremental proof. **Do not enable global TRACKER_CSRF_ENFORCE=1**: numerous
other native/JS/HTMX/multipart writes and session-account routes still need
complete HTTP/HTTPS positive and negative tests and a reviewed DEV rollback.
Report-only default is deliberately unchanged. No global strict enable
or issue #9 closure is justified without that evidence.

## Reproducibility #10
Keep the existing Release 569 44-package observed Python 3.13 pins and
Release 705 SHA-hashed private wheelhouse and independent replay. New
tracker_host_evidence746 captures and compares a bounded, explicit list
of shared-library SHA-256 digests and Chromium/OS identity in private,
no-clobber receipts without host paths. Actual installed DEV Python
baseline is audited read-only during source QA. No new downloads, packages,
venv, apt, browser installs or schema changes. Matching manually supplied
libraries do not establish full transitive ELF closure, independently
approved provenance, a full offline Chromium replay or rollback proof.
Keep issue #10 open until those real-host requirements are met.

## Workflow
One exact SHA branch, isolated DEV qualification, guarded DEV install,
signed PROD preflight and DEV-controlled PROD promotion. The release-event
PR #53 is never merged. Private logs/medical records stay off GitHub.
No full application backend suite is claimed.
