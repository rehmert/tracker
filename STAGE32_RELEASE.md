# Stage 32 — Vial transaction safety

## Changes
- Reserve SQLite write transaction before mutable reads for vial bulk edits, individual edits, deletion, filtering, preparation correction, and preparation deletion.
- Explicitly roll back write reservation on reconciliation validation failures.
- No schema migrations or data-file changes.

## Validation
- Python compileall passed.
- 12 targeted regression tests passed (test_phases_1_3, test_stage20_concurrency_isolation, test_stage28_pill_concurrency, test_stage31_compounds).
- Full regression suite and route-specific concurrent stress tests not performed.

## Deployment
Apply the archive to /opt/tracker after taking a backup. Restart tracker service. Test in staging first.
