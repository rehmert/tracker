# Release 508: Parallel DEV and PROD regression testing

## Motivation

Release 507 qualified on DEV in approximately 71 seconds (2,607 passing tests)
using 16 pytest-xdist workers, but the PROD deployment continued using serial
testing. PROD now has the same CPU/memory allocation as DEV, according to the
operator. This release removes the PROD-only serial restriction.

## Changes

- Both DEV and PROD guarded releases default to `pytest-xdist`
  with `--dist=loadfile` when `xdist` is installed and at least two CPUs
  are available. Worker count is the smaller of effective cgroup v2 CPU
  quota, CPU affinity, and 16.
- Both DEV and PROD use `systemd-run MemoryMax=6G` for their
  parallel-capable release worker. Under the operator's 8-GiB allocation,
  that leaves approximately 2 GiB outside the release worker.
- Explicit `--serial-tests` still executes the entire backend suite
  without xdist, capped at `MemoryMax=1G`.
- Without xdist, or with fewer than two CPUs, the full suite runs serially
  (the deploy log states the reason). Install `pytest-xdist` into the
  PROD Tracker virtual environment first if it is missing.
- PROD still requires a commit promoted to `main`; DEV browser checks,
  exact commit pins, isolated SQLite fixtures, restore tests, backup,
  deployment guards, and rollback checks remain unchanged.
- No production application code or database schema changes.

## First-release behavior and bootstrap

The standard release command runs whichever
`/opt/tracker/scripts/tracker-release.sh` is **already installed**.
Consequently, upgrading from Release 507 to 508 on PROD with the
existing 507 runner will still execute the tests serially. After
Release 508 is installed, all subsequent releases use parallel
testing automatically.

To use Release 508's **exact pinned runner on its first PROD
deployment**, a reviewer may extract the script from the already
promoted `main` target commit into a private temporary file, check
its checksum against `git show` and `bash -n`, then invoke it
with the usual pinned `--instance PROD --base --target --ref main`.
The script itself performs all existing worktree, data isolation,
recovery, status, SHA, service, main-ref and rollback checks. Never
execute a separately downloaded or unpinned deployment script.

Do not run another deployment while an existing release worker is
still active. `systemctl list-units 'tracker-release-*.service' --all`
and the deployment log provide status.

## Qualification before promotion

1. Check `pytest-xdist` availability on both virtual environments.
   If absent on PROD, install into its `/opt/tracker/.venv` before
   expecting parallel testing.
2. Candidate worktree: `bash -n`, Python compilation, focused
   `tests/test_prod_parallel_release508.py`,
   `tests/test_test_benchmark.py`, `tests/test_release_workflow.py`,
   `tests/test_testing_efficiency.py` and the full existing
   `pytest -n 16 --dist=loadfile` backend suite.
3. Deploy to DEV using the existing guarded release pipeline.
4. Promote the exact tested SHA to `main` only after DEV succeeds.
5. Deploy to PROD with the promoted pinned commit, checking
   `BACKEND_TEST_MODE=PARALLEL workers=16` (or a lower CPU-limited count),
   `RELEASE_WORKER_MEMORY=MemoryMax=6G`, full regression,
   verified restore and runtime smoke status.

Parallel testing is a release-workflow optimization, not a change to
serving application requests. Do not delete or skip regression tests
to improve release throughput.
