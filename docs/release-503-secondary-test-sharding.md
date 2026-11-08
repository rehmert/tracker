# Release 503 — Secondary Release 440 Integration Test Sharding

## Why this change

With 16 pytest-xdist workers and `--dist=loadfile`, the two slowest
Release 440 tests remained in the same module and were scheduled serially
on one worker:

- Full private secondary workflow with audit and cross-account checks:
  approximately 28–31 seconds.
- Authenticated readiness across all runtime flags: approximately
  16–18 seconds.

This was a scheduling bottleneck, not evidence that any assertions
were redundant. Removing or mocking the real HTTP/database work would
weaken the security acceptance gate.

## Implementation

- Keep readiness, lockdown, revoked sessions, PROD gating and workspace
  tampering tests in `tests/test_secondary_integration440.py`.
- Move the complete, unchanged private workflow regression to
  `tests/test_secondary_private_workflow440.py`.
- Place the original, unchanged disposable fixture and HTTP/database
  helper functions in `scripts/secondary_integration440_support.py`.
  Both test modules import the same fixture object; pytest invokes
  its function-scoped setup independently for each test.
- Update `scripts/tracker-test-gate475.sh multiuser` so the explicit
  security acceptance gate invokes *both* test files.
- Add `tests/test_secondary440_shard_safety503.py` to prevent test
  coverage or fixture-isolation changes during future refactors.

All six original test bodies and all original fixture/helper bodies were
verified unchanged against Release 502. No production application source,
security checks, DB schema, dependencies or systemd settings change.

## Qualification

Run the eight focused tests under two workers to confirm both file
groups collect and execute independently, then run the complete backend
suite under the same 16-worker, 6-GiB capped DEV configuration
qualified in Release 502. Compare wall time to the observed 82.74-second
full-suite baseline; confirm all original tests pass plus the new
sharding contract tests and the pre-existing skip.

Do not promote until the isolated full suite and subsequent guarded
DEV deployment both pass. PROD retains the existing serial full suite
until the installed release is verified on DEV.

## Limits

Each individual HTTP operation remains integration-tested with real,
isolated SQLite workspaces. This change improves scheduling but does
not attempt to reduce the intrinsic 28–31 second cost of the
full private workflow. Further improvements would require
profiling its application and fixture work separately.
