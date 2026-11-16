# Release 654 — Workout foundation (candidate)

Baseline: Release 653, `108bf3241bd747f6174dc7e65a8c01161af24e62`.
Branch: `release/654-workout-foundation`.

## Implemented

- Isolated workout equipment, session, and set models, using Tracker's existing SQLite Base and authenticated DB dependency.
- Machine catalog with four categories: selectorized, plate-loaded, free weights, bodyweight.
- Exact QR-code text / URL mapping, no network access to third-party links.
- Machine seat setting and setup notes.
- Start/resume/finish a workout, quick per-machine set logging (weight in pounds, reps, optional 1–10 effort), prior set history.
- Server-rendered mobile-friendly interface using existing Tracker forms, auth, origin and CSRF controls.
- Change-scoped syntax, template and integration test script: `bash scripts/tracker-release-scoped654.sh /opt/tracker/.venv/bin/python` **only in an isolated candidate worktree**.

## Scope and limitations

- Manual QR-code pasting, not direct in-app camera scanning.
- No routines, exercise programs, charting, bulk import, equipment photo lookup, offline synchronization or weight recommendations yet.
- This release uses the existing primary scoped application database. Secondary-user routes have separate read-only architecture and are **not** enabled by this change.
- A QR manufacturer link may be reused across multiple identical machines. The initial unique QR mapping intentionally rejects duplicates; later mapping can support per-gym physical variants.
- Workout weight is a recorded number in pounds; no comparisons between "per dumbbell", bar weight and loaded plates yet.

## Deployment is blocked pending reviewed schema workflow

**Do not deploy directly.** There are three new SQLite tables. Tracker's existing deployment runner does not presently recognize the new `app/workout_models654.py` file as a schema change. That is not approval to bypass backups or schema review.

Before DEV deployment:
1. Add and validate a fail-closed Release 654 schema-review gate to the existing deployment process.
2. Verify additive table creation against an isolated restored DEV database and test backups, without overwriting user records.
3. Run the focused test gate and necessary release-runner guard tests.
4. Approve an exact commit SHA and use the existing guarded DEV deployment workflow.
5. Only after DEV evidence is reviewed should a separate PROD promotion be considered.

No full Tracker test suite is necessary for ordinary Workout-only code changes; release-runner changes warrant a broader targeted safety regression gate.
