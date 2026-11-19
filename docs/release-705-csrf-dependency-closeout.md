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

The Release 627 historic snapshot originally had **161** unsafe route
declarations (83 prior candidate witnesses plus 78 unqualified routes).
The subsequent Release 654–704 additions include **38 further unsafe
routes**: 35 Workout endpoints, one COA attachment-identifier endpoint,
one saved-Food-edit endpoint and one Workout correction-undo endpoint.
Comparing Release 653 `108bf3241bd747f6174dc7e65a8c01161af24e62`
against Release 704 `24cb9ec47417e001c3f96dfed630e3b8b0264d93`
identifies the exact additions without guessed numeric thresholds.

The reconciler now records all 38 paths in an explicit disjoint
`POST_654_PLUS_UNQUALIFIED_ROUTES` manifest. A missing, unexpected or
incorrectly classified source route fails the historical inventory gate.
**None of the new routes becomes a CSRF witness merely by being listed.**
The current expected source count is **199** (83 preexisting candidate
routes and 116 unqualified); the previously source-mapped 27 additional
lifecycle routes leave **89 still without positive source evidence**.
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

The operator's fourth source preview finally passed the actual FastAPI 0.162
route canary: **3 passed**. It then stopped with 27 passing historical
regressions at `test_627_signed_route_reconciliation_stays_blocked`,
because the Release 627 reconciler still demanded the old 161-route
snapshot despite 38 legitimate post-653 route additions.

This is an obsolete historical source-count contract, **not** an observed
strict-CSRF bypass. The current candidate updates both the historical
reconciler and its tests together, pins the exact added method/path pairs,
keeps all 38 unqualified, and adds a fail-fast 627 inventory check before
the broader tests. Real DEV execution of the corrected candidate is
still required: no previous preview qualified it.

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

## Single release qualification and deployment limits

The candidate's exact nine-file diff comprises two new read-only
scripts, the audited Release 627 historical reconciler and its regression
test, two release-scoped/isolated preview scripts, two focused Release 705
test files (including the registered unsafe-route negative matrix), and
this document. It intentionally changes **no application code,
security middleware, server settings, requirements, database, JS, or
browser suite**. Source-preview success only means the new tools
are safe and report existing issues correctly.

The preview demands pinned 704 DEV main, a root systemd worker,
a clean checkout, a nine-file allowlist, detached candidate checkout,
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
