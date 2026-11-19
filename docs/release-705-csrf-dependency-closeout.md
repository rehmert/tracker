# Release 705 — Combined CSRF enforcement and dependency reproducibility closeout

**Baseline:** Release 704 on DEV and PROD at
`24cb9ec47417e001c3f96dfed630e3b8b0264d93`.
**Branch:** `release/705-csrf-dependency-closeout`.
**Issues:** [#9](https://github.com/rehmert/tracker/issues/9)
and [#10](https://github.com/rehmert/tracker/issues/10).

## Decision: one release, independent fail-closed acceptance

The user's goal is to resolve BOTH issues in the SAME release.
The repository does **not yet contain sufficient runtime evidence to call
either issue resolved**. This candidate provides a shared operator
readiness and artifact-lock procedure without risking DEV or PROD records.

The source gate passing does **not** authorize strict CSRF or certify
environment reproducibility. Do not close either issue or promote based
on only the Release 705 source preview. Do not turn on
`TRACKER_CSRF_ENFORCE=1` in installed hosts without the following
positive lifecycle and session-account coverage.

## Issue #9 — CSRF security acceptance

Tracker already supplies signed cookie/header tokens, mandatory
session-auth tokens, a global `TRACKER_CSRF_ENFORCE` opt-in, and a
multipart-safe route dependency. The existing isolated
`scripts/tracker-browser-qualify.sh` runs report-only and strict
HTTP/HTTPS reverse-proxy browser gates. NEVER replace those gates
with static or negative-only assertions.

The Release 627 historical baseline had **144** unsafe source declarations
(83 candidate witnesses and 61 unqualified). Releases 628–653 introduced
**20 more**, including **three Release 652 COA test-type catalog POST
routes** omitted from the earlier reconciliation inventory.
Consequently Release 653 had **164** declarations, not 161.

The subsequent Release 654–704 additions include **38 further unsafe
routes**: 35 Workout endpoints, one COA attachment-identifier endpoint,
one saved-Food-edit endpoint and one Workout correction-undo endpoint.
Comparing Release 653 `108bf3241bd747f6174dc7e65a8c01161af24e62`
against Release 704 `24cb9ec47417e001c3f96dfed630e3b8b0264d93`
identifies those 38 additions without guessed numeric thresholds.

The reconciler now records all 38 paths in an explicit disjoint
`POST_654_PLUS_UNQUALIFIED_ROUTES` manifest. A missing, unexpected or
incorrectly classified source route fails the historical inventory gate.
**None of the new routes becomes a CSRF witness merely by being listed.**
The current expected source count is **202** (83 preexisting candidate
routes and 119 unqualified); the previously source-mapped 27 additional
lifecycle routes leave **92 still without positive source evidence**.
At least 110 manual-review items and six session/account routes
require separate authentication and identity-aware review. A zero count
in any source report alone would not establish runtime clearance.

`scripts/tracker_csrf_closeout705.py` reports the existing conservative
readiness inventory, with `--json` for audit and
`--require-complete` as an intentionally blocking closeout check.
It does not mark any route qualified or toggle a configuration flag.

`tests/test_csrf_all_registered_negative705.py` additionally enumerates
the **current registered** ordinary unsafe routes (instead of relying only
on the frozen Release 627 source list). A disposable TestClient, with
strict mode enabled only in its own test environment and a synthetic
database, attempts both missing-token and forged-token requests on every
registered ordinary unsafe route. All must return 403. Session-owned
account/login/logout paths are deliberately excluded because they have
their own independent signed scheme; /secondary is separately mounted.
This is **negative security coverage**, not a claim that valid signed
data and file uploads work. Browser lifecycle positive evidence is still
required for every write flow over both HTTP and HTTPS.

### Release 705 preview defect corrected after first isolated run

The first isolated preview stopped **before sending any negative requests**:
the newly authored route test required `len(routes) >= 120` even though
the 161-item historical source-route inventory counts declarations that
are not equivalent to the current runtime `APIRoute` list (and includes
excluded session-owned scope). That hard-coded minimum had no measured
runtime basis. It was a test-design defect, not an observed CSRF bypass.

The corrected test instead requires 15 specific, verified critical write
routes across Compound, COA, Dose, Food, Lab, Notes, Protocol, Purchase,
Regimen, Supply, Vitals, Vials and Workout modules, then checks every
current registered ordinary write route with **both** missing and forged
CSRF submissions. An explicit observed-route/case-set assertion prevents
silently skipping an enumerated route. A signed but invalid Compound form
must still reach application validation (422), proving strict mode is not
simply blocking all writes.

A **second** isolated preview still stopped before requests, reporting
that all 15 critical write routes were absent. An attempted structural
fallback also failed in the third preview. The third diagnostic
identified the actual FastAPI 0.162.0 runtime layout: 76 top-level ASGI
entries, including multiple `fastapi.routing._IncludedRouter` objects
whose `path` and `methods` attributes are both absent.

**Verified root cause from the exact upstream FastAPI 0.162.0 source:**
`include_router()` uses lazy `_IncludedRouter` wrappers. FastAPI's
`iter_route_contexts(app.routes)` resolves these via
`_IncludedRouter.effective_route_contexts()`, returning effective
`RouteContext.path` and `RouteContext.methods` with nested prefixes
preserved. Reading either only top-level `APIRoute` objects or only
top-level `path`/`methods` inevitably misses the business routes.
The test now calls that exact framework iterator, and exercises it
against **real FastAPI nested include_router registrations**, not a
home-grown SimpleNamespace that could never catch this regression.

The strict 403 negative matrix and 15 critical-route sentinels remain
unchanged. The registered-route smoke runs first, followed by historical
source contracts, and exposes safe inventory diagnostics on mismatch.
No installed DEV or PROD configuration has been changed.

The isolated preview **must run** against the corrected exact SHA. All
three previous previews exited 1; no source-only pass, security
activation, reproducibility certification or deployment is claimed.

**Required before activating strict mode on any installed host:**

1. Reconcile the current actual registered unsafe-route inventory
   (including modules added since Release 627) with every native/HTMX/JS
   write, explicit signed positive persistence, and forged rejection.
2. Finish every unresolved browser lifecycle under both HTTP and
   HTTPS Host-rewriting proxy. Confirm that original multipart streams
   remain readable, and that native edit/save, bulk, async and
   delete routes still work with valid tokens.
3. Explicitly review or explain every dynamic/implicit source finding;
   retain immutable, route-specific runtime evidence rather than
   marking issues resolved via a synthetic boolean file.
4. Exercise authenticated session-owned routes and cross-account,
   secondary, and role/isolation negatives independently.
5. Run the one-time full 16-worker DEV backend suite and mandatory
   isolated report-only and strict Chromium suites. Then separately
   rehearse the configuration on DEV with a reversible host-level
   `TRACKER_CSRF_ENFORCE=1` update, full UI smoke and rollback.
6. Confirm operator-approved PROD deployment and rollback separately.
   Security flag enabling is an explicit operational change, not
   something the source-only Release 705 scripts perform.

### Fourth isolated DEV preview — historical fixed-count failure

The fourth source preview passed the real FastAPI 0.162 route canary
(**3 passed**) but stopped at the Release 627 historical source ledger,
which still expected 161 routes. A subsequent correction accounted for the
38 Release 654–704 routes, but the next preview again stopped at the same
guard because it omitted three Release 652 catalog writes.

Inspection of Release 653 source independently confirmed those exact three
routes: `POST /coa-test-types`, `POST /coa-test-types/{type_id}/edit`,
and `POST /coa-test-types/{type_id}/toggle`. The current candidate
records them explicitly as **unqualified**, changes the historical
accounting to 164 then 202, and raises detailed safe diagnostic counts
and missing route pairs on future source drift. The historic positive
browser witness checks are retained without relaxation.

This is an incomplete historical inventory, **not** an observed strict-CSRF
bypass. Real DEV execution of the corrected exact SHA remains required.

## Issue #10 — reproducible environment acceptance

Release 569 already records 44 exact installed distributions (including
`pip==25.1.1`) and 43 candidate constraints excluding pip. Release
570 provides opt-in disposable replay and artifact retention; Release
626 provides sanitized DEV/PROD inventory comparison. Merely copying
those pins into a second text file is **not** a reproducible build.

`scripts/tracker_dependency_lock705.py` takes an **existing local
wheelhouse** and produces exact SHA-256 artifacts for ALL 44 observed
packages. It rejects symlinks, unknown versions, missing/duplicate
wheels and non-private output directories. It writes an immutable
(mode-0600) manifest and a `--require-hashes` constraints file for an
**offline disposable** installation. It never downloads, upgrades
or installs software and never accesses the Tracker DB or credentials.

Example **after creating or recovering an approved wheelhouse** (do not
use the live /opt/tracker venv for a replay):

```bash
sudo install -d -m 0700 /tmp/tracker705-approved-lock
sudo /opt/tracker/.venv/bin/python \
  /opt/tracker/scripts/tracker_dependency_lock705.py \
  --create \
  --wheelhouse /path/to/private/approved-wheelhouse \
  --output /tmp/tracker705-approved-lock

sudo /opt/tracker/.venv/bin/python \
  /opt/tracker/scripts/tracker_dependency_lock705.py \
  --verify \
  --wheelhouse /path/to/private/approved-wheelhouse \
  --output /tmp/tracker705-approved-lock
```

Do not infer that an arbitrary wheelhouse is trusted just because the
files hash consistently. Review provenance, security advisories and
platform compatibility. Use the hashed requirements **only** for a
new disposable Python 3.13 environment with `--no-index`,
`--only-binary=:all:` and `--require-hashes`; confirm `pip check`,
exact installed package versions and the existing manifest auditor.

For #10 completion, additionally capture and retain:

- Sanitized current DEV and PROD pip/package, Python, SQLite and OS
  inventories; detect any drift from the 2026-11-11 observations.
- Original and approved wheelhouse bytes and trusted hash receipts,
  independent of the source repository.
- Playwright Chromium browser revision, executable/archive checksums,
  underlying OS libraries and exact platform compatibility.
- A fresh **independent** disposable installation, its full backend
  and HTTP/HTTPS Chromium results, and a second clean reconstruction.
- A tested rollback to the previously approved dependency/browser
  bundle, plus a recurring (at least monthly) vulnerability review
  and explicit update policy.

No unreviewed dependency update, network download, installed venv
mutation or requirement rewrite is authorized by this release.

## Browser suite inventory repair

A Release 705 isolated preview passed the ASGI CSRF negative canary
(**3 passed**) and historical 627 source reconciliation (**2 passed**),
then failed the Release 511 full-browser inventory requirement for
`tests/browser/test_consolidated_forms704.py`. A complete comparison of
45 `tests/browser/test_*.py` modules against the guarded full runner
found **15 omitted modules** from Workout 659–667 and mobile/UX 695–704.

The existing disposable standard 16-worker browser gate now registers all
15 omitted modules exactly once. A source-only Release 511 inventory check
runs at the start of the Release 705 preview before ASGI requests or
broader regression checks. All 15 modules remain in the guarded candidate
environment, not the live DEV or PROD service.

The Release 699/700 CSS parity modules need separate pinned-baseline preview
inputs and will be **skipped** during an ordinary full browser gate. Merely
listing them does not constitute executed parity evidence. The other
13 modules require real guarded browser execution before any promotion.

## Single release qualification and deployment limits

The candidate's exact thirty-file diff includes the CSRF and dependency
readiness scripts, audited historical reconciliation, source and full-browser
preview gates, the guarded browser qualification runner, focused Release 705
regressions, corrected legacy Vitals and Vials browser tests, and this document.
It changes **no application code, security middleware, server settings,
requirements, database, JS, or browser test sources**. The guarded runner
only registers existing test modules. Source-preview success does not
establish executed positive browser coverage.

The preview demands pinned 704 DEV main, a root systemd worker,
a clean checkout, a ten-file allowlist, detached candidate checkout,
disposable SQLite directory, no download, and syntax/focused historic
regressions. It prints the blocked issues rather than inventing a
security or reproducibility certification.

A later candidate within this **same Release 705 branch** must finish
the missing strict-CSRF browser coverage and reproducibility proof.
Because a subsequent patch would alter the candidate SHA, the
preview and full qualification must be repeated against that exact SHA.
When the security and dependency requirements truly pass, perform
one guarded DEV rollout using `--full-suite`, verify full HTTP/HTTPS
browser and restoration evidence, explicitly approve any host
configuration/dependency change, and use the standard DEV-controlled
production preflight and `--execute`.

**Do not deploy or close Issues #9/#10 from a source-only preview.**

## After successful 705 source preview: isolated full browser runtime stage

On 2026-11-19 the operator observed a successful exact-SHA source preview
at `fbf78b2b771ceb69712334c233fe2554c01ef6ce`:
the Release 511 inventory (1 pass), ASGI CSRF negative canary (3 passes),
Release 627 reconciliation (2 passes), and broader source checks
(44 passes). The source readiness report still lists **92** routes without
positive witnesses, **155** manual reviews, and **6** session/account routes.

A separate operator-invoked `scripts/tracker-browser-preview705.sh`
now runs the **existing full disposable 16-worker browser gate**, including
the normal browser pass, localhost HTTP and HTTPS proxy, strict CSRF browser
tests, and all 45 registered browser modules. It requires the exact Release
705 candidate SHA as an argument, a clean Release 704 installed DEV main,
the active installed DEV service, a root systemd unit, the deployment lock,
an explicit changed-file allowlist, and a detached worktree. This is a
**runtime qualification only**: no source deployment, systemd restart,
database migration, dependency install, downloaded artifacts, or CSRF flag
activation. Its temp source and data are discarded afterward. CSS parity
699/700 are expected to skip in the ordinary full gate unless the separate
pinned baseline inputs are provided and verified.

The shell runner and a focused source contract are included in the Release
705 source preview allowlist. Running it on DEV is the **next required
operator stage**; GitHub source review alone does not certify runtime success.
The full backend suite, independent offline wheelhouse replay, and positive
signed business flows still require separate evidence before approval.

### Browser preview synchronization correction

The first exact-SHA browser preview was blocked immediately by an active
`/run/lock/tracker-db-sync.lock`, before tests started. This was an
unnecessary coupling: the existing browser runner works exclusively on
disposable localhost HTTP/HTTPS services and temporary SQLite data, so
it does not participate in production database replication or migration.

The new full-browser preview now uses its own
`/run/lock/tracker705-browser-preview.lock` to serialize **browser
previews only**. It does not touch, wait on or clear the installed
database-replication/deployment lock. Instead, it requires installed DEV
main to be clean at the pinned Release 704 SHA before execution, verifies
it again after the suite, and fingerprints the locally reused HTMX vendor
asset before and after. If a concurrent deployment changes the installed
source or the trusted vendor byte content, the qualification fails closed.
The source and browser runner remain isolated from installed DB records.


### Isolated full browser QA — Release 522 Vitals fixture repair

A full disposable HTTP/HTTPS browser run reached **194 passed, 2 skipped,
1 failed**, then stopped in the Release 522 Vitals HTTPS proxy test:
the created Vitals row was found successfully, but the test still
waited for an obsolete `<a href="…/edit">` element. The shipped
`vitals.html` uses a native `GET` form with a visible **Edit** button
and hidden `days`/`events` parameters.

The Release 522 browser test now checks the actual native form, clicks
its Edit button through the HTTPS proxy, verifies the resulting GET
response, HTTPS origin and preserved query parameters, then proceeds
with its preexisting signed POST edit, persisted result and HTMX delete
assertions. A Release 705 static source regression protects the fixture
against reverting to the obsolete link selector. No app route, UI,
middleware, installed data or security behavior is changed. A fresh
exact-SHA runtime pass is still necessary before any positive browser
evidence can be counted.


### Full strict browser qualification — mobile Vials Reports disclosure

The exact-SHA a9685b3 isolated full browser preview passed **195 standard
browser tests** (2 skipped), then passed the separate native HTTPS Labs
module (2 tests). In strict-CSRF qualification **117 tests passed** and
**2 failed** in the same Release 603 Vials navigation test, parameterized
for HTTP and HTTPS. The existing Reports anchor was found but hidden.

The root cause is a stale browser fixture: Release 696 moved the optional
Vials section links into a collapsed native `details.tracker-flow696-more`
with a visible `More inventory tools` summary. The original Release 603
test tries to click Reports without opening that disclosure.

The updated test now asserts that Reports initially is hidden, clicks the
real native summary, verifies the disclosure and Reports link become
visible, clicks Reports without forcing pointer input, and verifies the
underlying `#tracker-inventory-reports` disclosure expands and the URL
fragment matches, for **both** HTTP and HTTPS. No app UI, CSS, server,
CSRF middleware, database, or configuration changes. A source contract
and Python syntax preflight protect this exact fixture. An isolated
DEV execution is still required for security acceptance.


### Strict Vials / Quick Entry test — Daily filter contract and focused preflight

Following the Reports disclosure fix, strict Chromium advanced to the Daily
filter assertions in the same Release 603 test. Both HTTP and HTTPS observed
**seven** visible Daily actions while the historical test expected five.
Current `quick_entry.html` explicitly marks seven as `data-quick-daily`:
Log Food, Log Water, Record Dose, Record Vitals, Log Workout Set,
Log Supplements / Meds, and Record Supply Usage. The JS filter correctly
keys on that attribute. No app bug or security bypass was observed.

The repaired fixture verifies the exact seven destination URLs, requires
all non-Daily cards to be hidden, checks live result counts, verifies
that the Water search narrows to its correct action, and ensures Clear
restores all actions and the accessible category state for both protocols.
The old magic count is removed instead of simply replacing 5 with 7.

To avoid another expensive full-suite failure from the exact same
navigation fixture, the guarded browser runner now permits a **single**
`--targeted-strict quick603` scope: both parameterized HTTP and HTTPS
cases against the disposable strict-CSRF server. The Release 705 wrapper
executes this focused scope first and only launches the complete
unchanged standard and strict Chromium suites if it passes. Targeted
success cannot certify full browser QA. No live data, settings,
dependency bundle, or user-facing application files change.


### Release 579 source-audit root cause: Release 668 workout offline-sync

The Release 705 strict browser preview at `921bc5d` passed the targeted
HTTP/HTTPS Quick Entry test, 195 regular browser checks (2 skipped),
119 strict-CSRF core checks, additional signed-write and negative probes,
and all 12 Release 579 strict runtime browser scenarios. It stopped
only when the old Release 579 source audit required exactly **50**
JavaScript callsites.

The initial hypothesis that the copied, Git-ignored HTMX vendor asset
caused this mismatch was **wrong**. A subsequent source-only diagnostic
reported `tracked=51 witnessed=2 catalog_get=2 coa647=1 coa651=1
vendor_unqualified=0`. The added source is
`app/static/js/tracker-workout-drafts668.js`, which implements
`POST /workouts/quick/offline-sync`. It uses
`credentials: "same-origin"`, the `X-Tracker-CSRF` header from
`window.trackerCsrfToken?.()`, and `redirect: "manual"`.

The Release 579 audit now expects **51 tracked application callsites**,
preserves exactly **two** Release 579 browser-witnessed callsites,
and counts **49** others as **not witnessed by Release 579**. It
explicitly requires one Release 668 callsite and its exact reviewed
POST request lines; mutations of endpoint, method, credentials, CSRF
header or redirect behavior fail closed. This is *source review only*,
not an executable positive/negative CSRF witness for workout offline
sync. The incorrect HTMX source-exemption code was removed.

Six older tests also hardcoded 50/48; their 575, 576, 578, 640, 648
and 651 source-ledger expectations have been reconciled together with
the 579 validator. All now assert the 668 source remains unqualified.
The Release 705 source gate executes these specific historical tests
before attempting any browser qualification, and the existing browser
runner repeats the narrow 579 review after copying its vendor asset,
before starting the HTTP/HTTPS servers. The changed-file allowlists
are exact. Runtime validation is pending and global CSRF enforcement
remains blocked.


### Release 580 strict HTTP/HTTPS edit navigation: source/API boundary

After Release 579 witness validation passed, strict-CSRF Release 580 reached
10 passed / 4 failed; failures were limited to compound and vitals
create/edit/delete workflows on both HTTP and HTTPS. Source review confirms
both affected list rows now offer a *native GET form and an Edit button*
instead of the older edit anchor.

The repaired Release 580 test clicks the actual GET Edit button without
forced interaction, verifies the HTTP/HTTPS origin and path of the returned
200 response, checks the preserved Vitals `days=3650&events=0` context,
and verifies a signed token on the edit page. Original signed POST edit,
unsigned 403 replay, HTMX delete, persistence and private receipt assertions
are retained.

The subsequent Release 582 Dose edit links and Release 583 Preparation
history edit links were separately compared with their shipped templates.
They still exist and were not modified. The browser runner now provides
one explicit `--targeted-strict workflows580` mode which runs all 14
Release 580 browser scenarios and validates its six private lifecycle
receipts, without claiming full qualification. The Release 705 preview
supports `--targeted-workflows580` and can run that scope alone after
source preflight; full mode additionally preflights both Quick Entry and
Workflows 580 before the expensive complete browser run.
No deployed application code or live data is modified.


### Release 583: calculator input lives outside its reconstitution POST form

The last isolated browser gate passed the Release 580 targeted tests but stopped
at Release 583 (two HTTP/HTTPS failures). Release 683 placed the BAC-water
calculator input `#rc-water` **outside** the `#recon-record-form683` form and
associated it with the native POST via `form="recon-record-form683"`.
The old test looked for `input[name="volume_ml"]` nested *inside* the
form, so Playwright waited for a DOM descendant that does not exist.

The repaired Release 583 test opens the real reconstitution disclosure
if needed, verifies the calculator input is visible and associated with
the actual native POST form, fills 2 mL, and verifies the unmodified
`FormData(form)` contains `volume_ml=2`. The existing signed reconstitution,
filtering/correction/deletion, forged 403 denials and synthetic stock
rollback checks are retained. No user-facing application code changes.

The guarded Release 705 browser preview offers a separate
`--targeted-preparations583` execution of the existing 583 strict
HTTP/HTTPS module, including its genuine fixture and private evidence
checks. A full preview first runs targeted 603, 580, and 583 cases
before the expensive full suite. Targeted success is explicitly not
full CSRF qualification.


### Release 580 intermittent Compound create table race (strict preflight)

The full-preview preflight intermittently failed the Compound create
case (HTTP only, 13 of 14 Release 580 browser cases passed) even after
the native GET Edit control repair. The failing line was a missing
new Compound table row immediately after a 303 POST response. The
test's prior `expect(body).to_contain_text(name)` can pass on the
`Added NAME` flash message; it does not establish that the redirect
has completed or that a persisted table row is visible.

The repaired test now independently GETs `/compounds` after successful
create, edit and delete POST/303 responses, checks the redirect
destination, and verifies each record in the newly loaded table.
It retains its real browser clicks, CSRF signed status, forged 403
rejection, record edit and deletion checks, and strict private
evidence receipt. This follows the existing race-safe pattern in
the Vitals workflow. No time sleeps, forced DOM interaction, test
skips or user-facing application changes were introduced.

Because the failure was intermittent, repeat the complete isolated
Release 580 targeted gate on separate disposable worktrees before
attempting another full browser run. A targeted result is not a
full-suite or global CSRF approval.


## Release 705 Issue #10 read-only offline readiness audit

After the exact candidate `ecc180cda992ddb8889da15f1ba32f2f25ba238e`
qualified the complete disposable browser suite (exit 0, 10m 51s,
3.9 GiB peak), the separate dependency reproducibility workstream
still remained blocked. The source had a filename/version/hash wheel
receipt generator but no trusted complete wheelhouse, wheel archive
metadata/ABI verification or independent reconstruction proof.
The Release 570 `--execute` tool fetches wheel bytes from the network
and must NOT be used for this offline read-only stage.

New `scripts/tracker_dependency_readiness705.py` adds a read-only
installed DEV comparison to the 44 observed Release 569 pins,
Python and SQLite versions, and `pip check` with the package index
disabled. It never runs pip install, upgrade, download or replay.
If a pre-existing, private `/tmp` wheelhouse is explicitly supplied,
it additionally requires the exact 44 SHA-hashed wheel inventory,
compatible wheel filename tags, ZIP metadata Name/Version and
WHEEL tags, Requires-Python and active non-extra dependency pins,
complete SHA-256 RECORD hashes and safe regular archive members.
No wheel is extracted or executed.

The dedicated `scripts/tracker-dependency-preview705.sh` is an
exact-commit pinned, DEV-only systemd worktree audit and intentionally
reports `DEPENDENCY_705_WHEELHOUSE=NOT_SUPPLIED` when none is provided.
A file that passes these checks is *not* independently trusted:
`DEPENDENCY_705_WHEEL_PROVENANCE=UNAPPROVED` and
`DEPENDENCY_705_REPLAY=NOT_EXECUTED` remain explicit. PROD package
parity, independently approved wheel origin and byte attestations,
two clean isolated installation/reconstructions, Chromium and OS
dependency pinning and rollback evidence remain separate blockers.
No new package downloads, installed dependency changes, live data
access, security activation or PROD actions are authorized.

Source and browser gates now include the new readiness test and
three-file allowlist additions. Because this changes the candidate
commit only in QA/readiness tools, the earlier full browser success
remains attributable to its *previous* exact SHA; it is not silently
reassigned to this SHA. Full DEV promotion remains blocked.


## Release 705 Issue #10 approved download-only PyPI wheel acquisition

On 2026-11-19 the operator approved acquisition of the 44 exact
Release 569 Python distribution wheels, with **no installation**.
A search of DEV /tmp, /root/.cache/pip and /opt/tracker found only
synthetic pytest wheel fixtures, not a real approved wheelhouse.

New `scripts/tracker_dependency_acquire705.py` is opt-in with
`--execute-download` and restricted to root on tracker-dev. It
creates an exclusive private `/tmp/tracker705-wheel-acquire.XXXXXXXX`
staging root and writes a separate private wheelhouse, exact pinned
requirements, and private hash receipts. Pip runs only `download`
with exact 44 pins, `--isolated`, HTTPS PyPI index, `--no-deps`,
`--no-cache-dir`, `--only-binary=:all:`, `--no-input` and a
bounded subprocess. `PIP_CONFIG_FILE=/dev/null` suppresses
global and site pip config that could inject unexpected indexes.
No preexisting cache, requirements or active environment is modified.
No browser is fetched.

After download it calls the previous read-only 705 archive and ABI
validator; verifies the exact 44-wheel filename/sha256 inventory;
checks each wheel byte count and SHA-256 against the named file in
PyPI's HTTPS JSON release API, disallowing mismatched, yanked or
unexpected-host artifacts; creates and re-verifies the exact SHA-256
lock and requirements file. It retains the private /tmp root on
success or failure and prints its location. **PyPI digest agreement
is not an independent provenance attestation**, vulnerability review,
browser pin, OS reproducibility, replay, rollback proof or Issue #10
closure.

New `scripts/tracker-dependency-acquire705.sh` is an exact-SHA,
DEV-only guarded acquisition wrapper. It checks clean installed
Release 704, active DEV, exact candidate branch, diff allowlist,
1 GiB free /tmp capacity, full Release 705 source qualification and
read-only installed Python baseline before any network call.
Acquisition is serialized using the existing dependency-preview
lock. All downloaded bytes stay in the private retained /tmp root
outside the transient candidate source worktree. It makes no
installed Python/DEV/PROD changes or global CSRF activation.

The changed-file allowlists and release source gate include
the new scripts and offline-only tests. A full browser pass on a
previous SHA is not silently assigned to the new SHA; the 705 release
remains unapproved pending the remaining security and independent
dependency replay evidence.
