# Release 666 — Workout Target Integration into Rapid Gym Mode

**Baseline deployed to DEV and PROD:** Release 665
`fe34a4060cd8b5933322d91d3e011206c87e21ef`

**Branch:** `release/666-workout-target-integration`

## Scope

Add a **read-only Planned Targets** panel immediately before the Rapid Gym
actual set logging form when both conditions hold:
1. A live workout is associated with a saved routine.
2. The currently selected equipment is an exercise in that saved routine.

The server already retrieves the authenticated routine and its ordered
`WorkoutRoutineItem655` rows. A small addition to
`app/routers/workouts659.py` identifies the exact routine item for the
selected machine and passes only the numeric `plan_item_id` to Jinja.
No target values travel to or from the server.

The `workout_quick659.html` template displays a compact panel
containing a direct **Edit plan** link and a labelled summary of planned
sets, reps per set and pounds. A small new JavaScript module reads
the existing Release 665 local-storage shape
`tracker.workout665.plan.routine.<routine_id>`, with item targets
addressed by the actual routine-item ID. No new persistence is created.

**Fallback behavior:**
- No active routine, a free workout, or a machine outside the active
  saved routine: no planned-target panel.
- No saved targets on this browser: a clear empty message.
- Invalid JSON, invalid schema, out-of-range or nonnumeric target
  fields: never display those values as valid planned targets.
  Each invalid field is displayed as unknown (—).
- Browser storage blocked/unavailable: an informative message rather
  than a page or logging failure.
- New targets saved in another same-origin tab, cleared targets, and
  returning from the planner in browser history: refresh the display
  via `storage` and `pageshow` events.

Targets remain optional, user-authored **intentions**, not recorded
workout sets. The panel is read-only. It does not automatically set
weight or reps fields; it does not populate, change, or submit actual
workout data. It cannot mark an exercise completed or affect rest
timers, routine ordering, or workout completion. The existing Rapid
Gym POST routes and existing target planner are unchanged.

## Scope and security

Only two previously deployed source files change, each pinned by
their exact Git blob before/after:
- `app/routers/workouts659.py`
- `app/templates/workout_quick659.html`

New files: isolated JS/CSS for the preview, new focused Python and
Chromium regression suites, this documentation, exact source review,
and DEV launch/test scripts.

No changes to schemas, data models, migrations, authentication,
dependencies, `localStorage` writer, set form, direct repeat
behavior, or existing workout POST endpoints. All database access
continues through `get_scoped_db390` and the existing active routine
relationship. Only the established local-storage per-routine key
can be read by the browser. Read values use `textContent`, not
HTML insertion or dynamic script execution.

**Privacy caveat:** Release 665 targets exist on the current browser
profile and are not synchronized. Another person who uses that
browser profile may be able to see them. This release does not
extend existing storage isolation across Tracker users.

## DEV acceptance and tests

- FastAPI route regression creates two routine items and one
  unrelated machine, starts the saved routine, verifies each chosen
  machine's correct item ID, verifies the unrelated machine and idle
  screens do not reveal a panel, records a real set, checks its exact
  actual weight/reps/effort and unchanged finishing workflow.
- Real Jinja body + shipped CSS/JS in Chromium at 320/390/393px.
  Tests real Release 665 storage format, absent data, matching item
  and routine, invalid fields/JSON, cross-routine isolation,
  same-origin tab updates, UTF-8 decoding, no phone overflow and
  unchanged actual logging inputs.
- Existing Workout 654–665 unit, HTTP and mobile tests rerun,
  including planner target writes, calendar, Rapid Gym 659/662,
  dashboard integration and deploy workflow guardrails.
- Exact scoped-review checks whitelist all added source paths and
  lock both existing-file blobs. DEV-only launcher confirms release
  665 baseline, instance identity, GitHub branch HEAD and exact
  target SHA before calling the established release runner.

Do not modify PROD directly; promote only a DEV-qualified Release
666 through the signed DEV-controlled promotion workflow.

## Manual checks

On DEV, select **Saved Routines → Plan & Compare**, save one or more
targets for a machine, then start that routine in **Rapid Gym Mode**
from the same browser. Confirm the targets appear above the set-entry
form. Navigate to another routine machine to see only that machine's
targets; navigate to an unrelated machine or begin a free workout
to confirm the panel is absent. Enter and save an actual set and
confirm the logged values came from the set form, not the targets.
Use another device/browser and verify planned values do not sync.
