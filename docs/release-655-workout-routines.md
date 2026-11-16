# Release 655 — Saved routines and fast set entry

## Baseline and scope
- DEV-qualified Release 654: 419e0c199d6a5dc373df7de1401953a056cac8d1
- Working branch: release/655-workout-routines-fast-logging
- GitHub is source storage only. No Actions, pull requests, hosted QA or cloud deployment.

## Added
- Saved named workout routines with 1–30 equipment entries.
- Append an exercise to a routine, move it up/down, or remove it (historic
  completed workouts and set logs remain intact).
- Start/resume a routine, associating its ID with a new workout session.
  When another workout is active, starting a different routine fails closed.
- Equipment appears first in the selected routine's order during an active
  routine workout; the remaining equipment stays accessible.
- One-tap Repeat Last Set copies the most recently recorded weight, reps and
  effort for exactly that machine, entirely server-side. A stale or mismatched
  source ID is rejected rather than silently logging unexpected values.
- Mobile-friendly forms and guarded duplicate-submit UX.

## Data protection
Three new additive tables only:
- workout_routines655
- workout_routine_items655
- workout_session_routines655

No changes to the Release 654 equipment, session or recorded-set schema.
No existing user data is overwritten or backfilled.

The existing authenticated get_scoped_db390 dependency is reused. App-wide
authentication, origin protection and signed CSRF policy apply to writes.

## Reviewed DEV qualification / deployment
- Verify exact base/target SHAs, clean DEV main at Release 654, valid DEV
  identity, active service, and exact candidate source blob.
- Inspect candidate in a detached worktree, run scripts/tracker-release-scoped655.sh
  against its isolated pytest data directory.
- Run additive schema review and focused Workout tests, previous 654 tests,
  targeted release-runner tests, and DEV missing-upload archive tests.
- Verify preexisting uploads; on DEV only reuse the Release 652 reviewed archive
  mechanism that explicitly permits exactly the one known missing COA file.
  Present file hash mismatches, invalid paths and unexpected missing records
  remain fatal. PROD is strictly checked.
- Run the usual verified migration database backup, recovery snapshot, fast-forward,
  service restart and runtime smoke. On failure, do not claim success.

Only start from DEV's installed exact commit 419e0c199d6a5dc373df7de1401953a056cac8d1.
Do not use PROD without exact-commit DEV approval and a subsequent deliberate promotion.

## Deferred
In-browser QR camera scanning, workout analytics, exercise targets, prescribed
progression, per-set edit/delete, rename/delete routine, and offline mode.
