# Release 570 — Disposable fresh-environment reproducibility replay

## Scope

Release 570 introduces a separately invoked, **opt-in, DEV-only** test
harness: `scripts/tracker_freshenv570.py`. The package versions, application,
database model, systemd service, global CSRF settings, and existing guarded
release scripts are **unchanged**.

It does **not** install anything into `/opt/tracker/.venv`. Do not run the
fresh-environment harness as part of an active guarded deployment, because
the standalone fresh test is intentionally heavyweight.

The observed dependency baseline is the committed 44-package JSON inventory
from Release 569; the 43-package constraints file omits pip, which is
explicitly downloaded and pinned separately at version 25.1.1.

## How to run from tracker-dev AFTER Release 570 is installed and qualified

First perform a non-executing preflight:

```bash
sudo /opt/tracker/.venv/bin/python \
  /opt/tracker/scripts/tracker_freshenv570.py
```

The expected marker is `DRY_RUN=PASSED`. This checks that the installed
checkout is clean `main`, the host is `tracker-dev`, source inputs are
present and the temporary filesystem has sufficient free capacity.

To run the isolated test (downloads **only** to a private `/tmp` sandbox):

```bash
sudo /opt/tracker/.venv/bin/python \
  /opt/tracker/scripts/tracker_freshenv570.py --execute
```

The tool deliberately uses official PyPI as its wheel index and the
Playwright browser installer to fetch a **separate** Chromium build.
This requires outbound access to the package and browser artifact servers,
sufficient temporary disk space and adequate memory for parallel tests.

### Seven isolated stages

1. Create a pinned-commit detached Git worktree under a new mode-0700
   `/tmp/tracker-freshenv570-*/source`, without modifying installed source.
2. Create a new Python 3.13 venv under the same private directory with
   system-site-packages disabled.
3. Download the exact pinned wheels and pip into a private wheelhouse;
   compute SHA-256 receipts of the downloaded wheel bytes.
4. Install only from that local wheelhouse, with `--no-index`, then run the
   exact Release 569 package/runtime audit and `pip check` inside the
   *new* venv (no live installation changes).
5. Download Chromium into the **private test HOME**, launch it and load
   an offline `data:` page. No existing root browser cache is needed.
6. Run the full non-browser backend suite with
   `TRACKER_TEST_PYTHON` pointing at the newly created venv and
   `TRACKER_DATA_DIR` pointing at disposable test data.
7. Execute Tracker's existing isolated browser qualification using
   a **temporary copy** of the browser runner in which its fixed
   `HOME=/root` entries are replaced by the private test HOME. This
   directs Playwright to the freshly downloaded Chromium and covers
   the existing normal and strict-CSRF browser QA. The tracked browser
   runner, live database, and installed server are not modified.

On any failure, the stage stops and the detached Git worktree is removed.
By default the private sandbox is removed after the run. Add
`--retain-artifacts` **alongside** `--execute` to retain wheel hashes,
downloaded wheels, venv, browser, and test-only logs under the displayed
`/tmp` path. Retained `/tmp` files are not durable backups and can be
large. Copy validated receipts and wheels to a separately protected backup
location only after confirming the result.

The test may take significant time. The script prints stage markers and
streams failures; it never silently falls back to the installed venv.
It does not restart or reconfigure Tracker on either host.

Expected success markers:

```text
REPLAY_PREFLIGHT=PASSED
FRESHENV_PACKAGE_BASELINE=PASSED
FRESHENV_CHROMIUM_LAUNCH=PASSED
FRESHENV_BACKEND_SUITE=PASSED
ISOLATED_STRICT_CSRF_BROWSER=PASSED
FRESHENV_BROWSER_SUITE=PASSED
FRESHENV_REPLAY=SUCCESS
```

## Limits and remaining Issue #10 acceptance gates

The evidence from this run is specific to **DEV's existing operating
system, CPU architecture and Python 3.13.5**. It is not yet proof of a
reproducible fresh operating-system deployment or byte-for-byte
equivalence with the original installed package artifacts. The
wheel-receipt hashes reflect packages downloaded during this replay.

Before changing the live requirements or closing Issue #10:

- Preserve a verified, protected wheelhouse and lock/hashes for the
  approved platform(s), and record the Playwright Chromium revision and
  relevant OS packages (not just its Python module).
- Rebuild on a second disposable host/container with pinned system
  dependencies and re-run the full isolated QA.
- Establish a separately reviewed dependency-update procedure and
  **rollback** by retaining the previously validated wheelhouse, source
  SHA, database backup and host compatibility data.
- Review dependency security advisories at least monthly and before any
  approved change; only upgrade in disposable isolation, never implicitly
  when running the standard source-only release runner.
- Continue to keep GitHub for repository history and code review only,
  not as the release execution engine.

No automated update cadence, cron job or externally hosted CI has been
created by Release 570. Any future dependency installation still requires
a separate reviewed deployment procedure, per `docs/release-workflow.md`.

Global strict CSRF remains report-only on DEV and PROD. The isolated QA
tests its strict setting **only in disposable processes**, and success
does not authorize enabling it on production.
