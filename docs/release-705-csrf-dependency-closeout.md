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

The conservative Release 627 source reconciler still has 51 unsafe
routes without mapped positive browser tests and at least 110 manual
review items; six session/account routes need separate authentication
and identity-aware review. Route additions since the frozen ledger may
increase this backlog; a zero count in that historic report alone
would not establish completeness.

`scripts/tracker_csrf_closeout705.py` reports the existing conservative
readiness inventory, with `--json` for audit and
`--require-complete` as an intentionally blocking closeout check.
It does not mark any route qualified or toggle a configuration flag.

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

The candidate's exact six-file diff comprises two read-only scripts,
two release-scoped/isolated preview scripts, one focused test file and
this document. It intentionally changes **no application code,
security middleware, server settings, requirements, database, JS, or
browser suite**. Source-preview success only means the new tools
are safe and report existing issues correctly.

The preview demands pinned 704 DEV main, a root systemd worker,
a clean checkout, a six-file allowlist, detached candidate checkout,
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
