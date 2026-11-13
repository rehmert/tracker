# Release 591 — PK strict-CSRF lifecycle and route forgery matrix

Baseline: Release 590, `18ab15f37654b23bff4d283fbb7c5c7a496adcd8`.

## Scope

Release 590's source-only gap planner reported 144 unsafe declarations,
19 browser-witness candidates, 125 remaining routes and 31 remaining
`/pk` routes. Release 591 adds two real Chromium tests **inside the
already-mandatory full strict browser module**:
`tests/browser/test_strict_csrf521.py`. No browser runner source
or allowlists change, avoiding source-contract churn.

### Positive and negative PK lifecycle evidence

Run independently on HTTP and HTTPS against the disposable strict-CSRF
localhost server:

- Signed JSON `POST /pk/compounds` adds a supported synthetic compound.
- Signed `POST /pk/scenarios` creates a scenario; GET confirms persistence.
- Signed `PUT /pk/scenarios/{sid}` edits it.
- Signed `POST /pk/scenarios/{sid}/doses` adds a planned dose.
- Signed `PUT /pk/scenarios/{sid}/doses/{did}` edits the planned dose.
- Signed `DELETE /pk/scenarios/{sid}/doses/{did}` deletes the dose.
- Signed `DELETE /pk/scenarios/{sid}` deletes the scenario.

For **each of the seven** operations, the browser's unsigned APIRequestContext
probe must receive HTTP 403; the actual browser fetch must send the signed
CSRF request header, the server must return the `valid` CSRF report header,
and the expected write status/data mutation must be verified.

A second test submits unsigned JSON to all **30 unsafe routes declared in
`app/routers/pk.py`** over both HTTP and HTTPS, requiring rejection
before handler execution. A backend source contract compares the matrix
against the actual router declarations. These additional checks are
**negative-only** and DO NOT qualify signed-compatibility of the
remaining PK paths.

## Route evidence and release workflow

Seven PK routes become **source candidates**, so if the complete
qualification passes the source-only report is expected to show 26
candidates and 118 remaining, assuming the same 144-route inventory.
These are not runtime-clearance claims; the report itself still
sets `global_enable_authorized=False` and the gap planner still
prints `CSRF_590_GLOBAL_ENFORCEMENT=BLOCKED`.

Existing Release 590 evidence module validation now also confirms
the mandatory 521 strict browser gate includes the 591 witness.
No app runtime, schema, dependency, UI template, service policy or
server configuration changes are included. No production account,
dose, compound, or vial data is used by the tests.

To save repeated setup, run changed source/backend tests in one
disposable worktree preflight, then **one full guarded DEV
qualification and deployment**. No extra targeted browser harness or
additional release is necessary. The full gate runs both new Chromium
cases as part of the existing required module. Standard PROD dry-run
and approval are still required before promotion.

## Explicit limitations

CSRF global enforcement remains report-only. The other PK paths
need positive functional signed-write coverage; 110 manual-review
items and secondary-account real-browser coverage also remain
separate work. Do not close the global CSRF tracking issue based
on seven PK witnesses.
