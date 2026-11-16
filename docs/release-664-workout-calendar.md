# Release 664 — Workout Calendar & Training Consistency

**Qualified production baseline:** Release 663 —
`20b9c0599ebf9ff4ea05ccddcd7130beaf6027a1`

**Release branch:** `release/664-workout-calendar`

## Scope

Adds an authenticated, read-only `/workouts/calendar` page using only
the previously deployed `WorkoutSession654` and `WorkoutSet654`
tables, through the standard `get_scoped_db390` dependency.

- **Month view:** Monday–Sunday calendar with prior/next month controls
  and a Current Month link. URL `?month=YYYY-MM` supports stable
  historical deep links.
- **Recorded training-day highlighting:** each date with at least
  one completed workout containing actual sets shows its number of
  completed sessions. Click the count to jump to the day summary.
- **Monthly summary:** completed sessions, distinct dates with completed
  workouts, and total sets across these completed sessions.
- **Session drill-down:** day groups in reverse date order list each
  completed workout (ordered by recorded start time) with a direct
  link to the Release 663 Workout Session Review, including individual
  set counts. Multiple workouts on one date count as multiple sessions
  but one training day.
- **Backdating:** sessions are grouped by their original recorded
  `started_at.date()`, never the creation order or browser time.
- **Entry points:** Workouts home, main Overview Workout Activity, and
  individual Session Review (which preselects the workout's month).

All dates use Tracker's configured America/New_York local wall-time
convention. The month is bounded and validated (1900–2100); malformed
`month` values return HTTP 400. Adjacent months are properly linked,
including December/January rollovers. At range ends, invalid
navigation links are omitted.

## Counting rules and limits

- A counted session has a non-null `completed_at` and at least one
  actual recorded set; an inner join and grouping by session ID
  exclude empty sessions and prevent extra sets from multiplying the
  number of workouts.
- Unfinished workouts and future-dated starts are excluded, matching
  the existing Release 661 dashboard summary semantics.
- A session's recorded start date determines its position. Individual
  `performed_at` dates do not move it to another date.
- There are no newly inferred sessions, future plans, streak-based
  behavior prompts, training targets, or recommendations.
- A day with two sessions is one training day and two sessions.
- This is a full month historical view, not the current dashboard's
  rolling 7/28-day metrics.

## Security, data and deployment

- Read-only GET only; no POST, database writes, external services,
  new persistence, schema, migration or dependency changes.
- Uses only the authenticated workspace's already-resolved scoped
  database session. The new route never opens a global engine.
- Four previously deployed source files change: application router
  registration, existing Workouts home, Dashboard's Workout Activity
  partial, and Session Review navigation. Their exact before/after
  blob SHA values are pinned by a fail-closed source reviewer.
- Entire candidate is allowlisted and exact-SHA pinned. The same
  release runner, DEV instance checks, backup and rollback
  protections are used as Release 663.
- No PROD deployment or main branch update occurs before
  successful `tracker-dev` qualification and a separate signed
  DEV-controlled PROD promotion.

## Tests

- Isolated SQLite regression with leap-year February 29, multiple
  workouts on one day, multiple sets on one workout, nonchronological
  creation/backdated ordering, out-of-month sessions, unfinished and
  empty workouts, and future-dated completed sessions.
- Strict month parsing, December/January rollover, and lower/upper
  supported month boundaries.
- FastAPI GET integration tests for stable anchors, counts, direct
  session-review links, current month, invalid selector rejection,
  expected Workouts/Overview/Session Review navigation, and no
  changes to session or set row counts.
- Real Chromium phone viewports (320, 390, 393 px) rendering the
  actual Jinja calendar body and shipped CSS; verifies no horizontal
  page overflow, accessible month controls, a two-session day
  anchored drill-down, and individual review links.
- Existing Workout 654–663, dashboard, source/prod release, and
  Rapid Gym/Overview mobile regressions run in the guarded DEV gate.

## Acceptance

Browse `/workouts/calendar` on DEV, navigate to prior months
containing backdated workouts, compare count badges against the
individual Session Review screens, and confirm two sessions on a
single day are two completed sessions but one training day.
An empty month must show all zero counts and a clear empty
message; an unfinished workout must never be counted.

The standard logged-set UI, Finish & Review, Rapid Gym Mode,
recorded Strength Progress, and session-scoped auth are unchanged.
