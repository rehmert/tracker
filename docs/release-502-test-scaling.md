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

## Acceptance requirements for release deployment

- All selected worker configurations pass twice, with identical full
  test counts and no intermittent failure.
- A faster count must be at least 10% faster than the lowest tested
  worker count, preferably based on the reported median.
- Effective LXC CPU quota and RAM capacity must accommodate workers
  and the guarded deployment's **systemd MemoryMax=1G** limit must
  be explicitly reviewed before any parallel deployment.
- Critical authentication, filesystem isolation, backup restore, dose,
  workspace and release tests stay inside the full-suite collection.
- Browser qualification, recovery backup, restore verification, runtime
  health checks, SHA pinning, fail-closed deployment and rollback remain
  mandatory.
- **This candidate changes benchmarking only.** The guarded DEV and
  PROD release scripts intentionally remain serial until separate
  qualification of the actual memory-limited deployment worker.

No deploys, no production dependency changes, and no background test
jobs are initiated by these code changes.
