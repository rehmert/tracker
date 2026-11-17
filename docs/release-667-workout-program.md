# Release 667 — Complete Workout Planning & Execution

**Qualified starting point:** Release 666,
`4062afbc2ca4273d2fdadaab17c804c477a9fc08`

**Protected release branch:** `release/667-complete-workout`

This is **one bundled release** containing A (Goals and Achievement),
B (Persistent Planning), C (Rapid Gym Improvements), F1 (Equipment/Exercise
Notes), F4 (Rest Presets), and F11 (Mobile UX). DEV must pass the reviewed
additive-schema gate before a separate signed DEV-controlled PROD promotion.

## Data model — additive only

Four new tables are registered in `app/workout_models667.py`:

- `workout_routine_config667`: routine-level default rest interval
- `workout_routine_targets667`: mutable, exact routine-item planned sets,
  reps, weight, exercise-specific setup notes and optional rest override
- `workout_session_targets667`: a snapshot of *complete measurable goals*
  bound to the actual newly started session and equipment; **not updated
  when the underlying routine plan changes**
- `workout_set_types667`: optional one-to-one annotation of an actual
  `workout_sets654` row as `warmup` or `working`. An absent annotation
  is treated as a legacy working set.

No pre-existing Workout 654/655 tables or historical rows are altered.
Existing data and reports continue to work. All new foreign keys reference
the already qualified Workout schema and are protected with checks.
A routine-item deletion may remove its editable future target; the
independent frozen session target remains tied to the original session.

## Plan and import

Open **Saved Routines → Plan & Compare (Synced)** (or the routine detail's
**Open Persistent Workout Program**) at
`/workouts/routines/{id}/program`.

- Save a full measurable goal of 1–20 working sets, 1–200 reps per set,
  and a finite 0–2000 lb load. All three numbers must be provided to
  count as a measurable goal. Leave all three empty for notes/rest only.
- Store up to 1,000 characters of exercise-specific setup notes, which
  complement the existing machine seat setting and equipment notes.
- Select rest defaults at routine level, optionally overridden by an
  exercise (supported intervals 30–600 seconds).
- Optionally **Import This Browser's Targets**, reading the Release 665
  browser-local key only when the user clicks the button. The signed,
  authenticated POST validates each item belongs to the routine, checks
  format and range, and saves complete sets/reps/load goals atomically.
  Imported numeric goals replace those of matching routine items, while
  preserving the saved notes/rest. Partial or invalid browser plans fail
  closed without any writes; no silent migration and no browser storage
  clearing is performed.
- Persistent goals are in the existing authenticated scoped SQLite DB
  and may be accessed from another device logged into the same Tracker
  account. Legacy browser-only plans remain available under their old
  `/plan` URL until explicitly imported.

## Rapid Gym Mode

Starting a saved routine captures the then-current complete goals in
the same database transaction as the session and its routine link.
A resumed session retains its frozen targets. Goals edited during
the session take effect only for a **later** session.

- For a machine with a frozen goal, show planned working sets × reps ×
  weight, the current number of qualifying recorded working sets, and
  recorded warm-up/working totals.
- **Use planned weight & reps** copies those two values into editable
  actual set fields **only when clicked**. It never saves automatically.
  The existing Save Set form, required inputs, and validation remain
  authoritative.
- Each recorded actual set can be marked **Working** (default) or
  **Warm-up**. The annotation is committed in the same transaction as
  the actual set. The existing Repeat Last Set preserves warm-up type,
  and the active-workout correction screen supports fixing a mistyped
  set type. Deleted actual sets cascade-remove their annotations.
- The existing rest timer starts after a *confirmed* set on the existing
  signed redirect; exercise/snapshot rest presets win over a globally
  remembered browser duration. Manual timer overrides remain available.
- The primary navigation points to the persistent program, while
  unchanged older browser-local targets remain available where no
  frozen goal exists.
- Mobile layouts prioritize readable goals, thumb-friendly buttons,
  set type selection and touch-accessible forms.

## Goals and historical results

`progress667` counts **only actual working sets** for a particular
session and equipment, and credits a qualifying working set only when
its actual weight is at least the frozen target load **and** its actual
repetitions at least the frozen target repetitions. Credited sets cap
at the frozen target-set count. The calculation does not infer 1RM,
form quality, training intensity or weight recommendation. A target
is achieved only if the full number of qualifying sets was recorded.
Warm-up sets contribute zero to target achievement.

The existing Session Review page shows frozen goals and actual
qualifying working/warm-up results for workouts having a snapshot.
The existing completed-workout overall volume remains an accurate
sum of *all actual logged sets*, including warm-up sets (this is
deliberately distinct from working-set goal achievement).

A workout predating Release 667 (or started without measurable goals)
does **not** acquire retrospective, invented targets.

## Safe rollout

- Release 667 explicitly extends the existing guarded release runner
  with `--db-migration --reviewed-workout-667`. The runner detects
  `app/workout_models667.py`, verifies the expected release ref,
  requires an exact-source review, and creates a verified migration
  backup of the database and present attachments before deployment.
- The signed remote PROD deployment wrapper also supplies these
  flags specifically for Release 667. Do not bypass these steps or
  perform database DDL manually.
- The source reviewer checks the exact Git blob pairs of every changed
  legacy file; new path allowlist; precisely four additive model classes,
  foreign-key and check constraints; unchanged 654/655 models; existing
  authentication/database scope; and DEV/PROD runner guards.
- Tests cover parsing boundaries, new schema and foreign keys, target
  snapshot immutability, warm-up exclusion, actual logging, import
  authorization, routine rest, and finished review.
- Chromium mobile tests render the shipped templates and JS at 320px,
  390px and 393px widths, including goal-copy intent, no auto-logging,
  rest presets, explicit browser import and no horizontal overflow.
- DEV reruns 654–666 Workout API and mobile regressions as well as
  deployment and backup safeguards before qualification.
- The standard exact-SHA DEV -> signed promotion -> PROD
  workflow remains mandatory.

## Acceptance walkthrough

Create or open an existing saved routine. Save a measurable goal
and a setup note in its persistent program. If desired, explicitly
import the old browser-local targets. Start the routine in Rapid Gym
and verify the frozen goal, note and exercise rest duration. Check
that copying planned values does not create a set. Save a warm-up
and actual working sets; verify progress excludes warm-ups. Repeat
and correct a warm-up label. Complete the workout and compare recorded
performance to the frozen goal. Edit the future routine goal and verify
that the completed session's historical target does not change.
