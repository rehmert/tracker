# Release 590 — CSRF witness inventory and prioritized gap batches

This release is a **readiness-analysis improvement**, not application behavior
or a strict-CSRF rollout. Its purpose is to turn an undifferentiated source
ledger into an actionable ordered backlog while retaining an explicit blocked
status.

## Evidence corrected

The native `POST /coas/new` multipart upload is now included in
`tracker_csrf_readiness588.py`'s *candidate* witness paths, reflecting
Release 588's real Chromium HTTP and HTTPS test. The separate Release 521
strict Chromium gate also covers the creation and verification path.

Candidate means the browser module is scheduled under the existing guarded
qualification workflow. Running the report does **not** execute Chromium,
inspect deployment evidence or certify any route.

## Gap planner

`scripts/tracker_csrf_gap_plan590.py`:

1. Loads the actual unsafe-route source ledger and 588 readiness report.
2. Refuses missing or phantom candidate routes.
3. Verifies explicit 587/588 evidence modules are present **exactly once
   in the full-only strict browser gate** rather than only in the Release
   589 optional batch.
4. Separates source candidate routes from routes still lacking a specific
   browser source witness.
5. Groups remaining routes by top-level URL workstream, ordered by
   descending number of unqualified routes and stable alphabetical ties.
6. Preserves unresolved JS/manual review metrics and highlights independent
   secondary-account coverage limits.
7. Always reports global enforcement **BLOCKED**, irrespective of counts.

Example after guarded DEV deployment:

```bash
/opt/tracker/.venv/bin/python /opt/tracker/scripts/tracker_csrf_gap_plan590.py
/opt/tracker/.venv/bin/python /opt/tracker/scripts/tracker_csrf_gap_plan590.py --json
```

## Qualification and next implementation batch

This candidate changes a source-only reporting script, a manifest, and tests.
It does not change the browser runner, runtime middleware, application
routers, installed database, service configuration or production strict-CSRF
mode. Accordingly, run focused Python tests from an isolated candidate
worktree, then **one full guarded DEV release**. Do not rerun every targeted
Chromium preflight for unchanged browser modules.

Use the planner's highest-volume unqualified URL workstreams to choose
the next consolidated batch of actual strict-browser tests; that follow-on
work requires real browser execution and signed/forged request assertions.
Secondary account TestClient evidence from Release 589 is not a blanket
browser-route authorization. Global enforcement stays report-only until the
remaining gates and separate operator rollout decision are complete.
