# Release 571 — Verified and retained Python/Chromium recovery artifacts

## Scope and boundaries

Release 571 adds `scripts/tracker_preserve571.py` and offline safety tests.
It is a **tooling-only source release**; there are no changes under `app/`,
the active `requirements*.txt`, database schemas, the Tracker systemd unit,
or strict-CSRF settings.

The new tool takes a **complete, successful, deliberately retained**
Release 570 replay and creates a root-only recovery directory under
`/var/lib/tracker-reproducibility`. It does not install dependencies,
upgrade packages, alter DEV/PROD data, restart services or access PROD.

The input replay is untrusted until checked. The tool validates:

- root-owned mode-0700 replay directory immediately under `/tmp`;
- mode-0600 replay log containing all backend, browser, strict-CSRF,
  package and Chromium success markers, matching the **installed SHA**;
- exactly 44 regular wheels with package names and versions matching
  the checked-in Release 569 inventory, including pip 25.1.1;
- every wheel's SHA-256 against the Replay 570-generated receipt;
- fresh Playwright's own `browsers.json` and separately installed
  Chromium, Chromium headless shell and FFmpeg revision directories;
- browser directory contents with SHA-256 for every regular file,
  rejecting absolute and out-of-tree symlinks;
- free disk capacity before writes, and copied byte equality prior
  to an atomic publish.

The archive includes a complete manifest of SHA-256 hashes and file
sizes, the exact wheel files, browser caches, the observed baseline,
candidate constraints, the successful replay log, source commit,
OS release, architecture, Python/glibc information and an OS package
inventory when `dpkg-query` is available.

The manifest is an integrity record, **not a digital signature** and
not proof of external backup durability. The archive is a protected
directory rather than a compressed installer.

## DEV-only procedure (after Release 571 qualification/deployment)

Run only on `tracker-dev`, as root. First prove the replay again while
retaining its sandbox instead of allowing the default automatic cleanup.
Use a **new root-only log**.

```bash
sudo bash <<'BASH'
set -Eeuo pipefail
umask 077
[[ "$(hostname -s)" == tracker-dev ]] || exit 1

LOG=/etc/tracker-release/release-571-retained-replay.log
[[ -d /etc/tracker-release && ! -L "$LOG" ]] || exit 1
: > "$LOG"
chmod 600 "$LOG"

echo "[1/4] Re-running fresh, isolated environment with retention"
set -o pipefail
/opt/tracker/.venv/bin/python \
  /opt/tracker/scripts/tracker_freshenv570.py \
  --execute --retain-artifacts 2>&1 | tee "$LOG"

ROOT=$(sed -n 's/^ISOLATED_ARTIFACTS_RETAINED=//p' "$LOG" | tail -n 1)
[[ -n "$ROOT" && -d "$ROOT" ]] || exit 1
grep -Fxq 'FRESHENV_REPLAY=SUCCESS' "$LOG" || exit 1

echo "[2/4] Read-only verification of retained evidence"
/opt/tracker/.venv/bin/python \
  /opt/tracker/scripts/tracker_preserve571.py \
  --replay-root "$ROOT" --replay-log "$LOG"

echo "[3/4] Preserving SHA-256 verified archive in /var/lib"
/opt/tracker/.venv/bin/python \
  /opt/tracker/scripts/tracker_preserve571.py \
  --replay-root "$ROOT" --replay-log "$LOG" --execute

echo "[4/4] Retained replay location for separate review"
echo "REPLAY_ROOT=$ROOT"
echo "REPLAY_LOG=$LOG"
echo "RELEASE_571_ARCHIVE_SEQUENCE=COMPLETE"
BASH
```

Expected final markers:

```text
WHEEL_HASHES_VERIFIED=44
BROWSER_REVISIONS_VERIFIED=3
REPLAY_EVIDENCE=VERIFIED
DRY_RUN=PASSED; --execute required to preserve
RECOVERY_ARCHIVE_VERIFIED=PASS
ARCHIVE_PRESERVATION=SUCCESS
RELEASE_571_ARCHIVE_SEQUENCE=COMPLETE
```

**Do not delete the retained /tmp replay until the archive has succeeded
and you've reviewed the archive path.** After success, the /tmp replay
can be removed manually from DEV when it is no longer needed; the
persistent archive will remain under the root-only directory.

For a future **read-only** archive verification, including after copying
the directory to a different root-owned system, run:

```bash
sudo /opt/tracker/.venv/bin/python \
  /opt/tracker/scripts/tracker_preserve571.py \
  --verify-archive /var/lib/tracker-reproducibility/baseline-<COMMIT>-<TIMESTAMP>
```

The verifier rehashes every archived payload file and checks the
manifest. It does not contact PyPI, install Python wheels, or start
Chromium. A verified archive is necessary but does not by itself prove
that the copied browser can launch on a differently configured OS.

## Recovery use and remaining gates

A copy of `wheelhouse` can be installed in a **disposable** compatible
Python 3.13 venv with pip `--no-index --find-links` and the saved
constraints. Browser binaries are in `ms-playwright`; point the
test-only `PLAYWRIGHT_BROWSERS_PATH` to that directory for a replay
after checking compatibility. Do not overwrite live venvs.

Keep a separate **off-host backup** of the root-only archive, with its
manifest and permissions; the archive on DEV alone cannot survive loss
of that host. Validate the off-host copy using its manifest before
relying on it.

This preserves the Linux x86-64 packages successfully reproduced on
DEV, not every future OS or architecture. GitHub Issue #10 remains open
for a separately rebuilt host/container, OS dependency qualification,
approved hash-locked installation process, and tested restoration.
Monthly security advisory reviews and separately signed, reversible
dependency changes remain required operational policy, not automatically
created tasks. Issue #9 strict-CSRF remains unaffected.
