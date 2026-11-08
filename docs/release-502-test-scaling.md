# Release 502: measured parallel backend testing

## Evidence from Release 501

The 2,591-test complete backend suite passed identically using
`pytest-xdist --dist=loadfile` at the following worker counts:

| Workers | Total seconds | Outcome |
| ---: | ---: | --- |
| 1 | 586.44 | 2,591 passed |
| 4 | 184.60 | 2,591 passed |
| 8 | 101.12 | 2,591 passed |

That is an observed 5.8x speedup at 8 workers (82.8% less runtime).
Only **one** run was performed per count, so do not yet declare this
a regression-proof release gate. No test was deleted or skipped.

## Next, measure additional DEV capacity

The experimental runner accepts 1 through 32 worker processes.
`scripts/tracker-test-benchmark.py` can now compare `8,12,16`
directly, without requiring an expensive repeat of the 1-worker run.
The lowest tested count becomes the baseline.

A sensible first target is 16 vCPUs and 8–12 GiB assigned to the
DEV LXC, provided the physical host can spare it. Actual cgroup CPU
quota and RAM limit are recorded in the JSON report; the 64-CPU host's
capacity is not necessarily available inside the container.

Suggested detached measurement in a **separate candidate worktree**:

    /opt/tracker/.venv/bin/python -u scripts/tracker-test-benchmark.py \
      --workers 8,12,16 --repeat 2 --timeout 1800

For speed, keep `--dist=loadfile`: tests from a given file execute in
one worker, limiting fixture interference. Even with separate SQLite
temporary directories per pytest process, test order and shared host
resources can create parallel-only failures.

## Verified repeatability on the 16-vCPU / 8-GiB DEV container

The second-stage benchmark completed six full backend-suite runs,
each passing **2,592** tests. The newly added benchmark test accounts
for the one-test increase from the Release 501 baseline.

| xdist workers | Run 1 | Run 2 | Median |
| ---: | ---: | ---: | ---: |
| 8 | 127.13 s | 125.02 s | 126.08 s |
| 12 | 101.54 s | 104.89 s | 103.22 s |
| 16 | 79.33 s | 79.28 s | 79.31 s |

16 workers were 37.1% faster than 8, and the two 16-worker
runs differed by only 0.05 seconds. This supports 16 rather
than increasing DEV resources further before a full deployment
trial. The cgroup probe reported 16 visible/affined CPUs and no
explicit v2 CPU or memory limit; the operator confirmed the DEV
LXC allocation is 16 vCPUs / 8 GiB.

## Guarded release integration

- DEV guarded releases use `pytest-xdist --dist=loadfile` with at most
  16 workers. The actual count is bounded by CPU affinity and, when
  available, cgroup v2 CPU quota. Missing xdist or fewer than two
  effective CPUs select the original full-suite serial path.
- `--serial-tests` explicitly forces the serial full suite, preserving
  the existing command and full test collection.
- DEV's detached systemd worker receives `MemoryMax=6G` by default;
  the 8-GiB container retains 2 GiB headroom for other services.
  With `--serial-tests`, its original `MemoryMax=1G` is retained.
- PROD remains **serial with MemoryMax=1G** until independently measured
  under PROD's actual CPU/memory allocation. We do not use DEV's
  16-vCPU result as evidence about PROD's configuration.
- A failed parallel test suite stops the release **before deployment**;
  it never reruns serial automatically to mask a failing test.
- Browser qualification, full test collection, rollback,
  verified recovery backups and runtime smoke checks remain unchanged.

The Release 502 installation itself is initiated using the already
installed Release 501 release runner and will therefore run serial.
The accelerated path applies to later guarded deployments after
Release 502 is installed and verified.

## Acceptance requirements for release deployment

- All selected worker configurations pass twice, with identical full
  test counts and no intermittent failure.
- A faster count must be at least 10% faster than the lowest tested
  worker count, preferably based on the reported median.
- Effective LXC CPU quota and RAM capacity must accommodate workers
  and the DEV guarded deployment's **systemd MemoryMax=6G** limit
  must be verified in an actual isolated release before promotion.
- Critical authentication, filesystem isolation, backup restore, dose,
  workspace and release tests stay inside the full-suite collection.
- Browser qualification, recovery backup, restore verification, runtime
  health checks, SHA pinning, fail-closed deployment and rollback remain
  mandatory.
- This candidate changes the release runner as well as benchmarking.
  No production application code or database schema is modified.
  PROD's full regression remains serial.

No deploys, production dependency changes, or background test jobs
are initiated by these code changes.
