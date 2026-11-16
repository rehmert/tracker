# Release 659 — Rapid Gym-Floor Mode

**Qualified DEV baseline:** Release 658
`8ff6dea1ac470e73fa886984238d958954de6d27`.
**Source branch:** `release/659-rapid-gym-floor`.

## Scope

Adds **Open Rapid Gym Mode** on Workouts. The independent screen at
`/workouts/quick` is optimized for real gym use:

- One selected machine at a time, with a native machine picker; saved
  routine machines appear first in their recorded exercise order.
- Start a normal workout or start an existing routine. Existing
  in-progress session is always reused; no duplicate workout.
- Previous recorded set prefills load, repetitions and optional effort;
  ±5 lb and ±1 repetition controls support quick touch adjustments.
  These are input adjustments only, not recommended workouts.
- A large Save Set button delegates to the **existing** validated
  `add_set654` logic, preserving limits, scoped user data, effort and
  live-session requirements. No new persistence path or schema.
- Repeat Last Set delegates to the **existing** stale-source-guarded
  `repeat_last_set655` endpoint and never accepts user-provided values
  for the repeated weight/reps. Double-click protection is supplementary.
- Routine progress is the count of distinct machines with recorded sets,
  not a clinical or performance assessment. Previous/Next links navigate
  saved routine ordering; free workouts allow manual machine selection.
- One tap to finish calls existing `finish654`, which retains existing
  completion semantics. Historical sessions remain read-only.
- Last up-to-12 sets on the selected machine during the current
  workout are displayed. Corrections remain available on the full
  Workout screen rather than creating a second edit implementation.

## Rest timer

- Client-side 60, 90, 120, or 180 second countdown with Start/Restart
  and Reset. A successfully saved or repeated set automatically starts
  it. A rejected write does not.
- The timer is keyed by the current workout session ID and preserved
  in **browser sessionStorage**, including when navigating to the
  next machine or reloading. It is not a durable server schedule,
  does not send notifications, and may disappear when the browser
  session ends or private storage is unavailable.
- Automatically starting is deduplicated by committed set ID so reload
  cannot restart the clock or fabricate a set. A manually started rest
  timer also remains local to that browser tab.
- Time is informational; Tracker does not prescribe exercise rest,
  weight progression, reps or intensity.

## Safety and deployment

- No database or model change, migration, backfill, dependencies,
  systemd changes, backup policy updates or changes to old Workout
  write endpoints.
- New quick actions use the same authenticated
  `get_scoped_db390` and Tracker's global origin / CSRF middleware.
- The new router delegates all writes to existing validated functions.
  No direct database writes from the router or new JS network endpoints.
- Source-only review allowlists the new router, template, CSS/JS,
  tests, DEV launcher and docs, plus exactly one shared router include
  and one Workout-page link.
- Focused application tests exercise valid/invalid logging, stale
  repeat rejection, routine order/progress, no-active failure, finish
  and existing 654–658 regressions.
- Focused real Chromium phone-viewport tests exercise touch steppers,
  automatic rest start, countdown continuity and reset using a
  disposable mocked page and the shipped JS. The backend server route
  is separately exercised via FastAPI integration tests.
- Use the exact-SHA launcher on **tracker-dev**. The established
  guarded release runner performs live attachment gate, isolated
  candidate tests, source snapshot, service restart and runtime smoke.
  PROD requires a later DEV-controlled signed promotion, never a
  manual PROD-host command.

## Acceptance

Open Rapid Gym Mode from DEV Workouts. Start or resume a saved routine,
select the first machine, log a set, and confirm the Rest Timer begins.
Use Next Machine, verify rest counts down, enter sets and return to
the previous machine. Verify your logged sets in the regular Workout
screen/history and the same progress stats. Leave PROD unchanged
until DEV qualifications and visual review pass.
