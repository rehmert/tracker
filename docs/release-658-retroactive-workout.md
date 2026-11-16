# Release 658 — Retroactive completed Workout entry

**DEV baseline:** Qualified Release 657,
`b9487d4b1fab176255b398833c51c9a2da79f042`.

**Branch:** `release/658-retroactive-workout-entry`.

## Scope

The Workout page gains **Log a Previous Workout**. The dedicated mobile
page allows date, local start and end times, optional existing saved
routine, and up to 40 actual recorded sets. Each row records an existing
machine, weight, reps, optional effort and optional set time. Four empty
rows are rendered initially; JavaScript can add and remove rows; all
validation is server-side.

The result is one **already completed** Workout session, and actual sets
appear in normal session history, per-machine charts, recent sets and
routine association. The user can backfill today's earlier gym session
as long as the end time is in the past.

A missing per-set time uses the manually entered workout start timestamp
for historical ordering, and the UI tells the user explicitly. The
server does not invent a precise actual set time or assign the current
time to retroactively entered sets.

### Constraints and protection

- User-supplied date must be within 2000–today, end after start on the
  **same day**, session duration at most 12 hours, end not in the future.
- One or more actual recorded sets required. Incomplete/blank rows are
  safely ignored; partial nonempty rows, malformed/unequal field arrays,
  nonfinite/out-of-range weight, reps and effort, unknown equipment IDs,
  nonlocal times and more than 40 sets are rejected without writes.
- Validation errors keep entered row values on the server-rendered page.
- Exact duplicate start/end window in this scoped DB is rejected to
  reduce accidental double submissions.
- Creation and all sets are in **one transaction**. The session's
  `completed_at` is supplied before commit; no live workout is created,
  ended, or modified. Active workout can remain active while entering
  a previously completed workout.
- No editing routes for finished sessions, no changing historical rows
  or previously saved sessions.
- All DB access uses `get_scoped_db390`; existing global auth, request
  origin and CSRF protections remain intact. No external APIs or network.
- No new tables/columns, schema migration, data fix, dependencies,
  systemd unit, backup-policy change, or release-runner change.

### Qualification and deployment

- Use only exact pinned SHA launch from `tracker-dev`.
- Source scope is reviewed against qualified Release 657.
- Focused Python route regressions include 654–657 and impacted release
  safeguards; Jinja parsing and JavaScript syntax are checked.
- The established release runner performs isolated tests, live attachment
  preflight, private source recovery snapshot, guarded FF-only install,
  restart and smoke check. PROD remains unchanged until separate
  DEV-controlled signed promotion.
- No full unrelated Tracker test suite; no GitHub-hosted CI.

### Verification on DEV

Open Workouts → Log a Previous Workout. Enter the actual date, local
start/end, choose one or more machines and enter previously performed
sets. Save, verify the completed session history and machine progress,
then verify any live workout remains unchanged. Invalid data should
preserve the entered form rows without writing a session. This can be
used to capture a workout missed earlier that same day.
