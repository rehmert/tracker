# Release 706 — Issue #9 and #10 follow-through

Base: Release 705 `4c084ade9063b3b01c2de0a4a055d2e23470b2a3`.
Scope: **source, diagnostic tests, disposable runtime evidence only**.
No modifications to app routers, strict-CSRF policy, service configs,
installed Python, browser files, DEV/PROD databases or user uploads.

## Known starting point (November 19, 2026)

- DEV and PROD reported successful signed Release 705 deployment.
- 705 source ledger: **92** unsafe routes lacking signed **successful**
  positive browser workflow witnesses, **155** manual review items and
  **6** session/account routes awaiting separate verification.
- 705 negative matrix exercised registered unsafe writes for missing and
  forged CSRF. This alone is never positive business-writes evidence.
- 44 pinned wheels were acquired, checked against PyPI SHA-256 release
  listings and exact RECORD metadata, and successfully reconstructed
  twice in network-isolated disposable Python 3.13.5 environments.
- Issue #10 was still blocked on Chromium/OS reproducibility, independent
  provenance/security audit, and rollback.

## Issue #9 — exact pending-route survey

`scripts/tracker_csrf_survey706.py` requires an isolated DEV synthetic
data directory under `/tmp/tracker706-csrf-probe.XXXXXXXX/data`,
`TRACKER_CSRF_ENFORCE=1` and `TRACKER_TEST_ISOLATED=1`. It uses the
FastAPI 0.162 lazy included-router enumeration already tested in Release
705 and the frozen Release 627/705 source ledger to classify every
remaining 92 route. For routes registered at runtime it sends a
cookie-paired signed token using an **invalid business payload**, and
records HTTP status and report header. It also saves the complete
static priority/manual review queue.

A valid header proves only that the token reached middleware. It
**does not prove a successful persisted business write**, the correct
failure of an unsigned forged write, HTMX/JS delivery, upload, form
navigation, or browser compatibility. No route is counted as a successful
positive witness by this survey. The 155 manual and six session/account
reviews remain open and global strict CSRF **must stay disabled**.

The survey writes a private evidence JSON
`csrf-survey706.json` under the retained evidence directory, including
exact per-route classifications and the review queue. The next
workstream must implement real signed positive browser lifecycles,
persisted state checks, and forgery rejection with seeded disposable data,
plus session/account-specific synthetic HTTPS browser tests. It must
prove that route coverage is complete before considering a globally
enabled enforcement switch.

## Issue #10 — Chromium, host libraries and isolated rollback

`scripts/tracker_browser_os_replay706.py` uses the existing Release
705 private wheel root:
`/tmp/tracker705-wheel-acquire.u523ry6c`.

The worker is mandatory `PrivateNetwork=yes`, verifies the exact
44 wheel hashes from the retained lock and receipt, and:
1. Runs Chromium via the previously installed root-owned executable
   without downloading a browser, using a `data:` local page.
2. Records executable SHA-256, Chromium version, `/etc/os-release`
   SHA-256, kernel, libc and each dynamically linked OS-library file
   hash. Missing required libraries fail.
3. Reconstructs two distinct local Python venvs from pinned offline
   wheels, reruns focused backend/ASGI qualifications, launches the same
   Chromium executable in each fresh venv, and fails on OS or binary
   fingerprint drift.
4. Takes a private snapshot of the first **disposable** venv,
   deliberately uninstalls `packaging` only there, verifies that
   dependency drift occurred, restores the pristine snapshot at
   exactly the same isolated path, re-verifies the 44-package baseline
   and `pip check`, launches Chromium again, and verifies its
   binary/library fingerprint.
5. Retains logs and report JSON in a private evidence directory,
   removing both venvs and all synthetic databases on exit.

The exercise proves reproducibility and rollback **within this host's
same existing OS image**. It does *not* independently reconstruct OS
packages; validate PyPI/OS/browser vendor supply-chain attestations;
scan 44 package versions for all newly disclosed vulnerabilities;
rehearse rollback of the installed live Tracker service on DEV/PROD;
or prove disaster-recovery restore of live user data. Those remain
blocking for complete Issue #10 closure.

## Guarded execution

`scripts/tracker-issue-review706.sh` must run as root on `tracker-dev`
inside systemd `PrivateNetwork=yes`, against a pre-fetched exact
Release 706 SHA. It requires installed clean Release 705, an active
DEV service, exact ancestor lineage, only six allowed 706 changed
paths, no concurrent dependency work, and a complete preserved 705
wheelhouse. It creates a detached worktree, runs Release 706 and 705
source qualification, then the CSRF survey and two-pass browser/OS
replay. It retains private evidence outside disposable worktrees.

**No GitHub main promotion, PROD deployment, global strict CSRF flag,
live dependency replacement, browser download or installed data change
is authorized by this evidence collection.**

### Closure criteria

**Issue #9:** all current unsafe routes reconciled to positive signed
HTTP/HTTPS Chromium workflows with persistent state verification and
paired unsigned/forged denial, all dynamic/JS/manual entries addressed
with audited evidence, session/account browser paths qualified, full
security regression run on a disposable isolated strict instance,
signed DEV qualification and PROD rollout with verified rollback.

**Issue #10:** exact Python/OS/Chromium versions and binary checksums,
reproducible independently sourced browser and OS dependency bundle,
separate supply-chain/vulnerability assessment, a tested guarded
restoration for source, dependency, database and browser changes,
and signed DEV/PROD promotion evidence. The 706 same-host replay and
disposable rollback are only part of these requirements.
