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

**Do not bypass the guarded release runner.** There are three new SQLite tables.
The Release 654 candidate now makes the runner classify `app/workout_models654.py`
as a schema change, requires `--db-migration --reviewed-workout-654`,
and invokes a fail-closed, exact-SHA additive-model review. The runner also
requires a verified pre-deployment database backup for migration.

Before DEV deployment:
1. Inspect the exact candidate commit, scoped CI evidence, and changed-file list.
2. Rehearse additive table creation on a restored, isolated DEV database backup.
3. Run the scoped release gate and focused release-runner regression tests.
4. Verify existing attachment integrity and complete the reviewed backup process.
5. Deploy to DEV using the pinned 653 base and approved candidate SHA:

```bash
bash scripts/tracker-release.sh \
  --instance DEV \
  --base 108bf3241bd747f6174dc7e65a8c01161af24e62 \
  --target <EXACT_654_COMMIT_SHA> \
  --ref release/654-workout-foundation \
  --db-migration --reviewed-workout-654
```

Only after DEV evidence is reviewed should a separate PROD promotion be
considered. PROD still requires exact-commit DEV approval before `--ref main`
is accepted.

No full Tracker suite is needed for ordinary isolated Workout changes. This
candidate modifies the release runner, so its scoped CI includes targeted
release-runner regression tests in addition to Workout tests.
