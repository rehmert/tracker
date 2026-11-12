# Release 579 — executable strict-CSRF browser write evidence

Base: Release 578 `16b6a65c99347d6218ade0cb4561b32150c5cd41`.
Issue #9 remains open. There is **no** change to installed DEV/PROD
`TRACKER_CSRF_ENFORCE`, authentication settings, app routes, database schema,
dependencies, backup paths, or systemd units.

## Runtime bundle

The existing isolated Chromium strict-CSRF gate now runs a standalone
`tests/browser/test_csrf_runtime579.py` module after the legacy strict
suites. Every test checks actual browser requests to the disposable
localhost candidate, positive signed response and forged unsigned
replay denial. Cases run separately for HTTP and host-rewriting HTTPS:

| Real UI / JS source | Request path | Cases |
|---|---|---|
| Mobile quick entry `tracker-mobile-quick528.js` — weight | POST /vitals | 2 |
| Mobile quick entry — blood pressure | POST /vitals | 2 |
| Mobile quick entry — water | POST /food/water | 2 |
| Notes source HTMX preview in `page_edit.html` | POST /pages/preview | 2 |
| Notes visual `notes_editor.js` fetch callsite | POST /pages/preview | 2 |
| Native compound creation form | POST /compounds | 2 |

These are **12 executable write-flow scenarios** across **four endpoint
paths**, not 12 distinct JavaScript callsites. The Notes visual fetch
probes a tracked callsite; the mobile fetch is one shared tracked
callsite serving three UI entry flows. Existing browser suites cover
additional routes, but this report does not infer their clearance.

## Fail-closed evidence gate

Each successful test emits a 0600 JSON record under
`/tmp/tracker-browser-qa.*/csrf-runtime579/`, with scheme, flow, method,
path, accepted status, rejected status and boolean witness flags.
No credentials, cookies, token strings, bodies or user data are stored.

`scripts/tracker_csrf_runtime_report579.py` requires an exact
twelve-file whitelist, exact 200/303 signed responses and 403 unsigned
rejections, and rejects unexpected fields and unsafe permissions.
The browser runner invokes this validator before writing
`ISOLATED_STRICT_CSRF_BROWSER=PASSED`. The ordinary DEV guarded
runner then continues its complete backend tests, backup/restore and
runtime checks. If any case or receipt fails, no DEV qualification
is issued.

`tests/test_release579_csrf_runtime_report.py` checks the receipt
contract, invalid statuses, extra fields, missing files, manifest
coverage, and shell syntax. The prior source inventory/ledger stays
unchanged and conservatively lists unmatched dynamic JS paths as
unresolved.

## Operational review

1. Run the existing pinned guarded DEV deployment to qualify.
2. Review the complete browser log for `CSRF_579_STRICT_RUNTIME_EVIDENCE=VERIFIED`
   and `CSRF_579_OBSERVED_SCENARIOS=12`, alongside full backend and
   isolated restore markers.
3. Verify automatic root-only DEV qualification receipt and conduct a
   separate human DEV UI review.
4. Run the DEV-controlled promotion preflight (no `--execute`), then
   explicitly approve signed promotion only after reviewing evidence.

The installed global enforcement flag remains report-only on both
hosts. Broader JavaScript callsite execution (most of the original
46), every unsafe route, secondary-account live browser flows, and
any separate reversible live strict-CSRF rehearsal remain open under
Issue #9.
