# Release 665 — Workout Program & Progression Planning

**DEV/PROD qualified baseline:** Release 664,
`06ffd87697f923808cfa76ea62004304883b9a3d`

**Branch:** `release/665-workout-progression`

## Scope

Adds a **read-only progression board for each saved routine**:

`GET /workouts/routines/{routine_id}/plan`

Available from:
- Saved Routines (Plan & Compare)
- Saved Routine detail (Open Program & Progression Planner)
- Rapid Gym Mode when a workout is associated with a saved routine
  (Review Routine Targets)

Each ordered routine exercise shows:
- The two latest **completed workout sessions with recorded sets**
  for the **same equipment ID**, ordered by recorded
  `WorkoutSession654.started_at`, not the insertion date.
- Recorded set count, total reps, the heaviest actual logged load,
  and session volume (sum of entered lb × reps) for each of the two
  sessions.
- The descriptive signed difference in heaviest load and volume
  between the two sessions, without implying a prescribed increase,
  improved strength or equivalent workload.
- Links back to each historical session review and machine analytics.
- A clear empty/baseline-only state for new machines and routines.

## Planned targets — browser-local only

The user can optionally enter **their own** next-session:
- Set count (1–20)
- Reps per set (1–200)
- Intended load in pounds (0–2,000)

These are *intentions*, not actual sets. They are never interpreted as
completed exercises or written into the Tracker database. This release
deliberately does not make recommended load changes, progression
predictions, exercise prescriptions or historical estimates.

Targets are kept on **the current device/browser only**, using
versioned `localStorage` under the current routine ID. The user can
clear all saved targets for that routine. Input values are validated
before browser persistence; invalid numbers do not replace previous
valid saved values. If browser storage is unavailable, inputs remain
editable but do not persist.

**Known limitation:** browser-local targets are not synchronized across
devices or browsers, and the same browser profile may share targets
between Tracker users with access to that device. Avoid shared
browsers for private plans. Server-side target persistence would
require a separate, explicitly reviewed database schema release.

## Existing data and security contracts

- No new tables, schema, migrations, new Python dependencies, or changes
  to stored workout records, completed sessions, workout routines,
  routine ordering, rest timer, exercise selection or Workout write routes.
- The new GET route checks the routine exists inside the authenticated
  `get_scoped_db390` workspace and restricts every set-history query
  to an item in that routine, matching the exact equipment ID.
- Only completed-session workout sets contribute to historical
  comparisons. In-progress, empty or unrelated exercise history does
  not appear. Backdated sessions follow their entered dates.
- Browser target script performs no `fetch`, `POST`, form submission,
  database mutation, cookie use or remote requests. It sets input values
  and local storage only and never inserts untrusted HTML.
- Exactly four existing files are changed: router registration,
  saved routine detail, saved routines list, and Rapid Gym Mode
  navigation. All four before/after Git blob pairs are pinned in
  the fail-closed exact-source review.
- The pre-existing strict DEV baseline/identity checks,
  source qualification, backup, rollback and DEV-controlled PROD
  promotion remain unchanged.

## Tests and qualification

- Isolated SQLite regression tests verify the two most recent
  completed sessions by start date, even with nonchronological
  insertion/backdated records, while excluding unfinished/empty and
  unrelated machine sessions and preserving routine ordering.
- FastAPI tests verify authenticated page rendering, existing history
  and analytics links, escaped user-entered machine labels, empty
  routine behavior, missing-routine 404, browser-only target inputs,
  and no set/session mutations on GET.
- Chromium tests use the shipped template and JavaScript at
  320/390/393px viewports. They verify browser target persistence
  across reload, routine-by-routine storage separation, local
  validation, clearing controls, no POST network requests, and
  mobile page width.
- The source gate validates exact changed files and existing blobs,
  Jinja/JS/Python syntax, and focused Workout 654–664 and mobile
  regressions on `tracker-dev`, not hosted GitHub CI.
- Only successful DEV qualification allows a later separate,
  signed DEV-controlled PROD promotion. Do not modify PROD directly.

## Acceptance

Open a saved routine and select **Open Program & Progression Planner**.
Check the last two actual completed sessions on each machine, including
one with backdated records. Enter some intended targets, reload and
verify they reappear on this browser only. Change to another routine
and verify drafts remain separated. Clear Saved Targets and confirm
no workout was logged, altered, or marked complete.
