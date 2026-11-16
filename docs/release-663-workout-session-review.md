# Release 663 — Workout Session Review

**Qualified baseline:** Release 662 — `efd5081a4f68c7f55d46db5e11c88660cfdc1a96`

**Branch:** `release/663-workout-session-review`

## Features

Adds `GET /workouts/sessions/{session_id}/review` for any existing
Workout session in the authenticated user's scoped database. Shows:

- Actual machine count (distinct equipment with recorded sets), set count,
  and total repetitions.
- Total recorded external-load volume, the sum of **recorded lb × reps**.
- Per-machine breakdown: machine and gym, sets, repetitions, volume,
  heaviest load actually recorded in this session.
- Session started / completed state, links to the original detailed
  set history, per-machine progress, overall strength analytics,
  Rapid Gym Mode, and the Workouts home page.
- Accurate empty-session state (all zeros) and in-progress label with
  a warning that totals can still change.
- No estimated one-rep maxima, invented bodyweight loads, coaching
  prompts, training targets, automatic logging, or new persistence.

Session summaries use existing `WorkoutSet654`, `WorkoutSession654`,
and `WorkoutEquipment654` tables and the established scoped DB dependency,
with all aggregation performed in SQL. Backfilled sessions are supported
without modification.

## Finish & Review

A second button (labelled **Finish & Review**) is added to both the
main Workouts page and Rapid Gym Mode. It submits a new
`POST /workouts/finish-review` route, which delegates the actual
completion to the **unchanged** `finish654` handler exactly once,
then redirects to the read-only review URL for that completed session.
The old **Finish Workout** buttons, forms, endpoints, and redirects
remain unchanged and work as before.

If there is no active session, the new action returns the exact
existing no-active-workout error redirect. No extra completion rows,
set writes, or migrations are introduced.

The detailed session history also gains a **View Session Summary** link.

## Safety, tests and rollout

- No schema, dependency, model, migration, backup, identity, session,
  authentication, CSRF, origin, or release-runner changes.
- Only four existing paths are changed: application router registration,
  existing Workouts screen, Rapid Gym Mode screen, and session history;
  all four are pinned to exact reviewed Git blobs in the source reviewer.
- The new route is scoped by `get_scoped_db390` and contains
  no `db.add`, `db.commit`, `db.delete`, engine access or network
  calls; only the original finish handler performs one existing mutation.
- FastAPI integration tests verify actual arithmetic, multiple
  machines including 0-lb bodyweight, history and machine-progress links,
  escaped untrusted machine names, an in-progress view, an empty session,
  missing session 404, read-only repeat GET, one delegated completion,
  double-completion rejection, and preservation of both old finish actions.
- Existing Workout 654–662, dashboard and mobile Chromium regressions
  remain in the change-scoped DEV qualification gate.
- Run the pinned SHA launcher on `tracker-dev` only. The established
  backup, identity, source, and scoped test guards must pass before a
  separate signed DEV-controlled promotion to PROD.
- GitHub is version control only; testing and releases execute only
  through existing Tracker DEV-controlled infrastructure.

## Acceptance

During an active Workout, use **Finish & Review** to reach an
individual session summary. Compare totals to the existing
full-set-history view. Check a past session through the
**View Session Summary** link. A session with no sets displays all
zero counts; a backdated session displays its original date. Verify
the previous Finish Workout action still behaves as before.
