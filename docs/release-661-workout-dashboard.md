# Release 661 — Workout Activity on Tracker Overview

**DEV baseline:** Release 660,
`6a11a1a76a3d32d64bd8b98788dcc2eab4c0bece`.

**Branch:** `release/661-workout-dashboard`.

## Feature

Adds a customizable **Workout Activity** section on the existing Tracker
Overview page. The section uses the user's existing scoped SQLite workout
tables, and keeps dashboard ordering, show/hide preferences and the main
route's authentication and other contents unchanged.

- Completed workouts in the last **7 calendar days** (inclusive today).
- Distinct days containing a completed workout with at least one set in
  that same 7-day period.
- Completed workouts and distinct training days over **28 calendar days**.
- Five most recent completed workouts with actual sets, sorted by the
  original `started_at` (backfilled workouts appear in their correct
  chronological order), each with recorded set and distinct machine
  counts, linked to its actual workout history.
- **Open Rapid Gym Mode** (or Resume when an unfinished workout exists),
  **Strength Progress**, and **All Workouts** shortcuts.
- Clear zero-data message with a link to log a previous workout.

A session counts only if `completed_at` is set and at least one
`WorkoutSet654` exists. Every distinct calendar date counts only once,
even with two completed workouts that day. An unfinished workout, an
empty session and a future-dated start are excluded from frequency.
The SQL uses a correlated EXISTS to avoid counting one session
multiple times when it contains multiple sets.

## Privacy and limitations

- All queries execute under the authenticated Dashboard route's
  preexisting `get_scoped_db390` session, never a global/non-user DB.
- Read-only: no new write handlers, no database schema changes,
  migrations, imports, API requests, backup changes, dependencies or
  background jobs.
- Today is Tracker's configured local calendar date. Rolling windows
  include today and the previous 6 / 27 calendar days; this is not a
  Monday-to-Sunday week.
- No normative workout frequency targets, streak pressure,
  estimates of strength, or exercise advice.
- A workout with no sets is not counted as training.
- The new section uses unused dashboard panel ID `9`, so the
  existing browser-local section visibility and ordering controls
  continue to work.

## DEV qualification / rollout

- Exact-SHA DEV-only launcher based on the already-qualified
  Release 660 deployment process. All installation, regression testing,
  backup/restore checks, and smoke checks execute on **tracker-dev**.
  No GitHub CI and no manual PROD deployment.
- Fail-closed review of the exact modified shared Dashboard route and
  template; any unreviewed changes to other existing features fail.
- Isolated SQL unit tests prove 7/28-day boundaries, same-day
  multi-session vs distinct-day counts, 5 recent sessions ordered by
  original date, backfills, one-session-with-multiple-sets, exclusion
  of unfinished/empty/future sessions, and read-only behavior.
- Real Dashboard GET integration test ensures the panel, session
  links and quick paths render using the app's ordinary scoped DB.
- Phone-size Chromium smoke renders the actual Jinja partial and CSS
  and tests layout overflow, quick links, and the actual dashboard
  personalization JavaScript's show/hide for panel 9.
- Existing Dashboard and Workout 654–660 regression tests run in
  the change-scoped gate.
- PROD remains on Release 660 until a separate DEV-controlled,
  cryptographically signed promotion after successful qualification.

## Verification

Open Tracker Overview. Confirm Workout Activity shows your recorded
completed-session frequency and recent workouts. Click Rapid Gym Mode
and Strength Progress. Use Customize dashboard to hide/show the new
Workout activity panel; verify dashboard layout saves as expected.
