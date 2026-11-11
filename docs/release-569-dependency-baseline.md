# Release 569 — Observed dependency baseline and drift detection

## Purpose

DEV and PROD on 2026-11-11 each reported the same **44 installed Python
packages**, on Python **3.13.5** and SQLite **3.46.1**. Both passed
`python -m pip check`. This release records that measured baseline and
adds a **read-only** drift check. It does not reinstall, upgrade, or pin
the live service.

The application and security policy are unchanged. This is a scripts,
tests and documentation release, eligible for the existing guarded
source-only deployment. No schema migrations, environment edits, systemd
changes, production dependency installation, or app restart are needed.

## Files

- `docs/dependencies/observed-2026-11-11-py313.json`: exact 44-package
  observed inventory, including `pip==25.1.1`, plus Python and SQLite
  versions.
- `docs/dependencies/candidate-constraints-py313.txt`: **43 candidate
  exact-version constraints** (excluding pip itself), not passed to any
  live `pip` invocation.
- `scripts/tracker_dependency_baseline569.py`: compares every installed
  distribution and the interpreter/SQLite versions with the manifest;
  validates that the constraints are consistent with the manifest; runs
  the existing interpreter's read-only `pip check`; returns failure on
  differences.
- `tests/test_release569_dependency_baseline.py`: offline, synthetic
  parsing, drift, and fail-closed behavior tests. No live host access.

## Running the read-only check from DEV after deployment

```bash
cd /opt/tracker

sudo .venv/bin/python scripts/tracker_dependency_baseline569.py \
  --instance DEV

sudo ssh -n -T -o BatchMode=yes -o StrictHostKeyChecking=yes \
  root@tracker-prod \
  'cd /opt/tracker && /opt/tracker/.venv/bin/python scripts/tracker_dependency_baseline569.py --instance PROD'
```

Expected on matching environments:

```text
BASELINE_PACKAGES=44
INSTALLED_PACKAGES=44
CANDIDATE_CONSTRAINT_PINS=43
DRIFT_COUNT=0
PIP_CHECK=PASS
BASELINE_AUDIT=PASS
```

Exit status 0 means the observed baseline matches. Exit 2 means version,
interpreter, or SQLite drift, or incompatible installed requirements. Exit
1 means the baseline/constraints are malformed or the inventory could not
be read. No action is taken automatically on drift.

## What this is NOT

**This is not yet a reproducible, hash-locked install.** The observed
environment may contain packages installed outside the declared
`requirements.txt` and `requirements-dev.txt`. Constraints do not
automatically install every package listed, and the current candidate
constraints lack wheel SHA-256 hashes. Matching installed versions do not
prove a future installer can reproduce the same wheels on another host.

The Playwright Python package is listed, but the corresponding **Chromium
browser binary and operating-system libraries** are not captured by the
Python inventory.

The existing guarded runner intentionally rejects changes to root
`requirements*.txt`. Neither these files nor any code in this release
changes that guard or changes the installed dependency set.

## Issue #10 completion gates (still pending)

1. In an **offline or otherwise isolated disposable environment** using
   Python 3.13, test a fresh install constrained by these version pins;
   compare the complete resolved package set against the manifest.
2. Capture the exact package wheel artifacts/hashes and the Playwright
   Chromium build and OS dependency requirements; document availability
   and recovery if packages are withdrawn.
3. Run the complete isolated backend and browser QA suite against the
   recreated environment without touching DEV or PROD databases.
4. Define an operator-reviewed update cadence, security advisory review,
   and a rollback procedure with a retained, tested wheelhouse.
5. Only after the separate dependency qualification and approval should
   the actual installation requirements be pinned or changed using a
   **separately reviewed deployment** (not the source-only release path).

Do **not** close GitHub issue #10 solely because Release 569 passes.
Global strict CSRF is also unchanged; GitHub issue #9 remains open.

## Release and approval procedure

1. Qualify the exact Release 569 SHA on tracker-dev through
   `scripts/tracker-release.sh`; verify backend, browser, restore and
   runtime markers. Review the DEV operator-facing workflow.
2. Run the newly installed read-only baseline checker on DEV.
3. Approve and run the permanent `scripts/tracker_promote568.py` from
   tracker-dev, which signs, promotes and remotely invokes the guarded
   PROD runner using existing SSH keys.
4. On both hosts, run the read-only baseline checker. Keep the issue open
   until the fresh-environment validation gates above are complete.
