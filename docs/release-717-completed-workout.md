# Release 717 — Edit a completed workout

**Base DEV Release 716:** `26aac9d781b2dacb0b73d00158d3737201ea814e`
**Release branch:** `release/717-completed-workout-edit`

## User flow

Finish your workout as usual. Then from **Workouts → Recent Workouts**, select **Edit Workout** beside the completed session. The same entry point appears in **Session Review → Edit Workout** and **Workout History → Edit Completed Workout**.

The completed-session editor lists sets in recorded order with machine name, within-machine sequence, weight, repetitions, set type and timestamp. Expand **Edit or Remove This Set**. You can use the existing audited value correction (load/reps/effort/type) or **Remove This Set**, with an explicit confirmation checkbox and a required reason (prefilled *Extra set logged*). Each successful removal returns to the same editor, showing the updated number of sets and removal audit history. A session stays completed.

## Data integrity

- **No new schema or migration.** Reuses established `ChangeAudit` to store a transactional deleted-set snapshot and reason. If the set had earlier corrections, their complete before/after audit records are preserved inside this snapshot before the old FK-restricted rows are explicitly removed.
- The completed workout's start/completion times, equipment identity for remaining sets, and frozen routine goals do not change.
- Removal deletes the actual extra set, so existing review/analytics/progression/CSV aggregates naturally recompute instead of counting a phantom set or introducing another eligibility filter.
- Unconfirmed/malformed requests, noncompleted workouts, missing sets, or sets that belong to another session are rejected.
- All endpoints reuse established scoped authenticated SQLite dependency and global CSRF/origin enforcement, with same-transaction audit and set removal.
- The audit history, including earlier corrections for removed sets, is visible on the editor itself and in Tracker's private global audit history.

## Qualification and release

`scripts/tracker-qualify717.sh`: exact-commit isolated DEV qualification in detached worktree, disposable SQLite, private network, clean installed Release 716 baseline, strict changed-file allowlist and Release 604 static preflight.

`scripts/tracker-release-scoped717.sh` runs:
- Syntax/import checks and scoped backend tests of completed-session navigation, audit, counts, prior correction preservation, wrong-session rejection, absent confirmation and active-session rejection.
- Existing Workout654/657/663, corrections668 and integrated recovery674 regressions.
- Strict signed mobile Chromium on HTTP and HTTPS: create machine, log two sets, complete workout, find Edit Workout, remove one, verify review total reduces to one and audit persists.
- Browser test registration check. The complete unrelated app suite is intentionally not part of the small scope.

DEV installation only after exact qualification receipt is passed, using `scripts/tracker-install717.sh`. PROD requires user authorization for every release, read-only preflight, then guarded DEV-controlled promotion; Release 716 must already be promoted on PROD before a normal 717 promotion.
