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

## Purchase-specific positive lifecycle extension

The full strict Chromium runner now also executes
`tests/browser/test_csrf_purchase_children627.py` against both isolated
schemes. Using a synthetic purchase and the existing synthetic compound
fixture, it verifies signed create/edit/delete of purchased supplies,
creation and deletion of BAC-water inventory, child-vial creation/deletion,
and deletion of the emptied purchase. Each write is paired with a
tokenless 403 attempt and checks persisted SQLite values/absence. This
extends evidence for seven purchase-specific routes without depending
on production inventory. It is scoped to the disposable browser QA
database, and is not a general authorization to enable strict CSRF.

The candidate remains unqualified on DEV. Full backend and browser
passes—including the new suites—are mandatory before promotion.

## Low-cost targeted validation before the single full release

Release 627 explicitly adds
`scripts/tracker-browser-qualify.sh WORKTREE PYTHON --targeted-strict csrf-batch627`.
It launches the same disposable localhost backend/TLS proxy and exercises
only the three new 627 browser modules. It emits
`TARGETED_CSRF_BATCH627_SCOPE=NEW_BROWSER_ONLY_NOT_FULL_QUALIFICATION`.
This mode is restricted to a detached candidate worktree and must never
be interpreted as a full DEV release receipt or permission to promote.

Run focused Python regressions for the route matrix separately in the same
detached worktree. Only after all targeted failures are resolved should the
ordinary one-time guarded DEV qualification begin. The full strict browser
gate still runs all existing browser modules, including new 627 modules,
and PROD remains unchanged until signed approval.

## COA signed multipart browser lifecycle extension

A fourth targeted/new full-gate module,
`tests/browser/test_csrf_coa_lifecycle627.py`, now covers actual
native signed PDF upload to `/coas/new` and browser-context signed
edits, verification (persisted notes/status) and deletion of the
synthetic certificate. Each write has an unsigned 403 counterpart, and
the entire lifecycle runs over both HTTP and the isolated HTTPS
host-rewriting proxy. It reuses only synthetic vial fixtures from the
isolated browser runner. The two remaining COA assignment/unlink
operations still require explicit positive witness mapping.

The newly added tests are candidate source only: neither targeted nor
full Chromium execution has yet been observed for Release 627.

## First targeted run evidence — failed, not qualified (2026-11-14)

Operator log `/etc/tracker-release/release-627-targeted-20261114T230201Z-50dIfh.log`
used candidate `2a3996778735eeb1ff2ed3409c49f69f2cb690a4`.
The isolated backend matrix passed 111/111, and 30/30 Chromium
workstream-forgery probes passed. The first positive lifecycle module
passed two protocol cases but failed four cases:

- Notes/page HTTP and HTTPS creations succeeded; the test compared a
  machine-generated title to Tracker's title-cased UI output.
- Lab HTTP and HTTPS signed update returned 303, but an exact-text HTML
  assertion did not find the analyte and did not establish persistence.

The candidate test now compares displayed titles case-insensitively
and asserts the changed pages/lab analytes/protocol state directly in the
disposable SQLite database. This is an **unexecuted corrective commit**;
there is no rerun evidence yet.

The operator-created external script `/root/tracker-627-safe-preflight.sh`
has a separate shell bug: `qa` was declared `local` inside worker, but
the EXIT trap runs when local function scope has ended and raised an
unbound-variable error under `set -u`. This script is not part of the
repository. Operator must initialize the worktree variable in global
scope before a new run, and inspect/remove any orphan disposable
worktree from the first run. No installed DEV/PROD app code changed.

The previous failed QA must not be counted as a passing Release 627
qualification. Purchase and COA modules did not execute.

## Second operator run (2026-11-14 23:13 UTC) — failed, root cause fixed in source

Candidate `f774f2e123c64ebe33fd2d92f4d42c70039d1b81`:
111/111 backend tests and 30/30 HTTP/HTTPS negative Chromium
tests passed; 2 protocol lifecycle cases passed, 4 pages/lab
cases failed. The direct SQLite checks established the source of
the false "success": `page.request.post(data=fields)` submits JSON
rather than the `application/x-www-form-urlencoded` required by
FastAPI's `Form` parameters. The routes returned a 303 validation
redirect while leaving data unchanged. This was a test-client bug,
not demonstrated CSRF acceptance. Corrected all such posts in the
native lifecycle, purchase-child and COA modules to
`page.request.post(form=fields)`. Success now requires actual
persisted data and field values, not just HTTP 303.

The external root launcher also has a second variable-lifetime error:
`local log="$1"` inside `worker` is out of scope when the EXIT
handler executes. Change that to a global assignment as well.
These two local launcher repairs (`qa` and `log`) are distinct
from the GitHub candidate and must be made before rerunning.

The new `--targeted-strict csrf-positive627` mode reruns only
the three previously unqualified positive Chromium modules, one
worker each; it does not repeat the 111/30 passed cases. This
is not a complete release qualification or deployment approval.

## Latest observed operator result — targeted positive modules PASSED

The operator reported these exact terminal markers for the corrected
positive-only candidate `e32515600c06626fece3168ed231e5d706e2b0cb`:

```
MODULE_EXIT=0
TARGETED_CSRF_POSITIVE627=PASSED
TARGETED_CSRF_POSITIVE627_SCOPE=NEW_POSITIVE_BROWSER_ONLY
ISOLATED_SERVER_STOPPED=YES
ISOLATED_BROWSER=PASSED
RELEASE_627_TARGETED_PREFLIGHT=PASSED
```

This is operator-provided targeted browser evidence, not a full DEV release
receipt or independent re-execution by the reconciliation script.

## Source-qualified route inventory — conservative reconciliation

`python -m scripts.tracker_csrf_reconcile627 --json` is a deterministic
read-only route-to-positive-test reconciliation. The historic 590 inventory
continues to report 144 unsafe routes, 83 earlier source candidate witnesses,
and 61 routes without earlier mapped positive witnesses. The new 627 modules
have 19 disjoint additional normalized route witnesses, leaving **42 routes**
without mapped positive lifecycle evidence. None of the 19 is promoted to
full runtime qualification merely by its source reference.

The 19 are precisely:

- Protocols: 3 (create, toggle active, delete)
- Pages: 3 (create, edit, delete)
- Labs: 3 (create report, add result, delete report)
- Purchases: 7 (BAC-water, purchase delete, supply create/edit/delete, vial
  create/delete)
- COAs: 3 (edit, verify, delete)

The 6 independently session-protected account/login/logout routes are
among the 42 and still need identity-aware browser evidence. The original
110 dynamic-JavaScript/implicit-form review items also remain open; no
automatic inference or dismissal occurred. The 590 inventory is preserved
as a historical conservative baseline. The 627 reconciler is a new
overlay, not a rewrite of that historical inventory.

**Release 627 remains blocked for global CSRF enforcement.** Full guarded
DEV qualification, account isolation, remaining route coverage and manual
queue disposition remain required before a separate, explicitly authorized
enforcement rollout. PROD remains on Release 626; this candidate makes no
application or dependency changes.

## Protocol and blend preview coverage added — source only, not yet executed

The guarded Release 627 branch now includes two additional isolated strict
Chromium suites: `test_csrf_protocol_remaining627.py` and
`test_csrf_blend_previews627.py`.

The protocol suite signs and rejects forged requests for calculation
(read-only), date updates, save, save-and-add-item and duplicate. It
asserts unchanged inventory on calculation, SQLite field persistence for
saved changes, retained row count, duplicate creation and deletion of
synthetic protocol records. Both HTTP and HTTPS are parametrized.

The blend suite signs three *read-only* preview workflows: normal
liquid-source, dry-source reconstitution what-if and same-compound
waterfall preview. It creates its own strictly disposable synthetic
vials and asserts stock remains sealed, dry vials remain dry, and no
blend was recorded. These previews are **not** evidence for the four
blend recording endpoints. Source and destination values are synthetic
test fixtures only.

The 627 source overlay now maps **27 of the historic 61 gaps**, with
**34 routes without source-mapped positive witnesses**. Of those
27 mapped routes, 19 have passed the previously reported targeted
positive-only browser run; the 5 added protocol and 3 blend-preview
routes have *not* yet been executed on DEV. The historic 590 plan
continues to report 61 gaps because it is an immutable baseline, not
a current qualification receipt.

A lightweight `--targeted-strict csrf-new627` option runs only these
two new suites with one worker per suite. Its result must be observed
before treating any of the eight additions as positive runtime evidence.
The separate full guarded DEV QA and 110 manual-review items remain
outstanding. Strict global enforcement and PROD are unchanged.

## First full guarded DEV attempt: QA blocked before installation (2026-11-15)

Candidate `81817de878f33e9b0c9c686f3b9e07726be17497`
failed two parameterized HTTP/HTTPS blend preview browser cases during
fixture setup with `sqlite3.OperationalError: no such table: compounds`.
The test incorrectly imported `app.db.SessionLocal`, whose engine was
already bound to the pytest worker's default data path instead of the
independent temporary browser server's `TRACKER_DATA_DIR`.
The isolated backend was running and the tests had **not** reached the
signed-blend preview assertions.

Correction: the pytest module now binds a dedicated SQLAlchemy engine
directly to the prevalidated `/tmp/tracker-browser-qa.XXXXXXXX/data/tracker.db`
file and sets the local worker's TRACKER_DATA_DIR to that disposable
directory before importing Tracker models. It enables SQLite foreign
keys and disposes the engine after test cleanup. A focused regression
asserts the absence of the default `app.db.SessionLocal` import and
presence of explicit isolated binding. This is an unexecuted correction
until the next guarded DEV run.

The first guarded attempt printed `EXIT_STATUS=1`; there was no
successful release install or full DEV qualification receipt.
The new candidate must pass the original guarded runner before it can
be installed. Strict global CSRF enforcement remains unchanged.

## Second full DEV attempt: historical 584 source contract blocked backend

Candidate `519b10cf14415837544eba510d1dadef51391b5c` reached
`3252 passed, 1 failed, 16 warnings` in the full backend suite before
`--maxfail=1` stopped qualification. Failure:
`test_584_targeted_qualification_is_strict_only_and_cannot_forge_full_pass`
requires the exact original Release 584 allowlist expression within
`scripts/tracker-browser-qualify.sh`. Release 627 had replaced that
expression while extending accepted targeted modes. This is a source
contract compatibility regression; it does not demonstrate a failure
of the app's CSRF enforcement.

The corrected runner restores the original Release 584 expression
verbatim as a functional condition, then permits the three added
Release 627 targeted modes in a separate functional OR condition.
An additional Release 627 regression test enforces both allowlist
fragments and their order. A local Bash syntax and allowlist
accept/reject smoke of the replacement fragment passed, but the full
host backend suite has **not** been rerun against this correction.
No successful DEV install is claimed.

## Third guarded DEV attempt — legacy COA HTTPS display assertion

The operator's full release attempt on candidate
`5bc5fce55e477976cb70a7303fdb123af19c20da`
failed `test_csrf_multipart588.py` under HTTPS after the genuine
native multipart upload returned 303, the browser navigated to the new
COA detail page, and the rendered editing textbox contained the
expected unique laboratory name. The failing test used
`expect(page.locator("body")).to_contain_text(name)`. HTML input
values are not part of the page's body text, so that assertion did not
measure whether the name persisted. The operator-provided Playwright
ARIA snapshot explicitly displayed the new laboratory value inside
the edit textbox and the uploaded document link.

Both the original 588 browser test and the newer 627 COA lifecycle
browser test now assert the actual edit input's value with
`to_have_value(...)` and require the uploaded-document link.
The original signed response code, CSRF reporting, unsigned denial
and multipart content-type assertions are retained. A source regression
guards both modules against the misleading body-text check.

The correction has not yet been runtime-tested. This failure occurred
before installation; no full DEV qualification receipt or PROD
authorization is claimed.

## Fourth guarded DEV attempt — Release 511 inventory gate (2026-11-15)

The next operator run stopped in the full backend suite at
`3362 passed, 1 failed, 16 warnings`. The failing
`test_511_every_browser_module_in_disposable_qualification`
test classifies browser modules not explicitly marked strict-only as
belonging to the standard report-only browser gate. The six newly
introduced `tests/browser/test_csrf_*627.py` modules are strictly
dependent on a separate disposable CSRF-enforcing backend and were
already correctly scheduled once in the full strict gate. The prior
Release 511 source-contract test had not been extended to recognize
them and incorrectly expected them in the report-only section.

The Release 511 contract now explicitly classifies those six as
strict-only and removes the three carefully delimited Release 627
targeted-only replay blocks from source counting. It still enforces
exactly one occurrence of every discovered module in its mandatory
full-mode section, and separately checks that targeted sections cannot
emit the full clearance marker. All 35 browser entry points (including
the separate root browser modules) reconciled against the pinned
runner source under the source-audit logic.

To prevent another expensive full-suite failure, the existing Release
604 focused regression list now includes the Release 511 browser
inventory test and the Release 584 targeted allowlist test; an
additional Release 627 regression directly invokes the full 511
inventory contract. These source checks are **not** a substitute for
running the actual guarded Chromium and full backend suites on DEV.
No PROD or global strict-CSRF rollout is authorized.

## Fifth candidate: focused source-contract literal newline bug

The first focused gate for candidate
`16c4895326f05dd2b6a3c0cf22b3ba242ada0b99`
stopped at `197 passed, 1 failed` in
`test_627_release511_inventory_scopes_new_browser_modules_strict_only`.
The newly extended Release 511 test used
a double-backslash-escaped string where the Python delimiter
was intended to be a line break on either side of `fi`.
The targeted-only replay block ended in actual newlines, so the
source split raised `ValueError`; this was a test code error.

The corrected Python test now uses real Python newline escapes,
`tail.split("\\nfi\\n", 1)` as displayed in source (one
backslash per escape). A source-level replay of the 511 inventory
check successfully matched all three targeted sections and all
35 expected browser entry points with no missing or duplicate
standard/strict full-gate entries. That reconciliation does not
replace actual host Python pytest and full browser qualification.

## Sixth guarded DEV attempt — legacy browser worker cardinality

Candidate `eb7a090441ef7e6fdca5d15fe4aba26e042e751e`
reached `3481 passed, 2 failed, 16 warnings` in the full backend
suite. Two historical source contracts, Release 594 and Release 598,
assert exactly three occurrences of the four-worker Chromium invocation
`-n 4 --dist=loadfile`. The optional targeted-mode optimization in
Release 627 had made the shared module-runner invocation dynamic
(`-n "$workers"`), leaving only two literal occurrences. The
observed failures were test contract failures, not evidence of altered
CSRF behavior.

Correction: the module runner now builds an explicit four-worker
command for the mandatory full browser qualification and a separate
one-worker command for optional non-deploying targeted probes. The
legacy literal invocation is present three times, the original
`WORKERS=4` source marker is restored, and the Bash pipeline continues
to capture pytest's actual exit status. The Release 587/588, 589, 594,
597 and 598 runner contract tests have been added to the pre-release
focused regression gate alongside 511 and 584. A Release 627
regression also checks both command paths.

Source review verifies the required three literal invocations and
the historical four full-mode sections. This correction still
requires guarded DEV runtime qualification before installation.
