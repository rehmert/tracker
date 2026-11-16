# Release 662 — Rapid Gym Mode UX Refinements

**Qualified DEV baseline:** Release 661
`7456380bfe191cdc011a7dc692bd8c8cce59d1ed`.

**Branch:** `release/662-rapid-gym-ux`.

## Changes

A source-only progressive enhancement to the existing
`/workouts/quick` screen; the existing form endpoints and persistence
are unchanged.

- **Machine selector:** selecting another machine navigates immediately
  to that machine's existing GET page, without tapping Go. The Go button
  stays in place for browsers without JavaScript.
- **Searchable machine directory:** one collapsed **Find a machine by
  name** directory lists all server-rendered equipment links. Typing
  filters by machine name or gym locally; no network call or new
  backend endpoint. The selected machine is marked with
  `aria-current="page"`. The list remains usable when JS is off.
- **Finer load/repetition adjustments:** alongside the existing
  ±5 lb and ±1 rep buttons, additional ±2.5 lb and ±5 rep controls
  let the user adjust before saving. They reuse the Release 659
  stepper behavior and the same server-side validation. All values
  remain user-decided rather than automatic recommendations.
- **Restore prefilled values:** a native `type=reset` button resets
  all inputs to the last recorded machine set supplied by the server
  (or clears inputs when there is no prior set), without creating
  a workout entry.
- **Closer routine navigation:** an additional Previous / Next
  Machine row sits immediately after set-entry buttons, so the
  next exercise is easier to reach. The existing routine navigation
  below the Rest Timer remains as a fallback. Both use authorized,
  existing equipment IDs from the active routine.

## Protections and behavior

- No table, model, database migration, new query, write route, auth,
  CSRF, origin, session, deployment-engine, backup or dependency change.
- `app/routers/workouts659.py`, `tracker-workouts659.js`, the rest
  timer and existing Workout methods are **unchanged**.
- New `tracker-workouts662.js` only submits the existing
  **GET** machine selection form and filters links already produced
  in the authenticated page. It never performs network writes or
  manipulates session storage.
- The session-keyed Release 659 rest countdown continues across
  machine navigation and reloads. Session history and set corrections
  remain unchanged.
- All displayed equipment names and gym labels are escaped by the
  existing Jinja templating system, including search attributes.
- The new machine directory is collapsed by default, scroll-limited
  and usable on small-screen devices.

## DEV qualification

- DEV exact-SHA launcher verifies qualified Release 661 baseline,
  candidate source and live instance identity.
- Source reviewer enforces an allowlisted change set and checks the
  **exact Git blob** of the single modified preexisting template.
- Focused FastAPI tests inspect the rendered selection directory,
  routine links, correction-safe existing set endpoints, injected
  unsafe names, and ensure a read-only GET causes no set writes.
- Chromium phone-sized tests run **both shipped 659 and 662 scripts**,
  checking ±2.5 lb and ±5 reps, restoring set fields, searching by
  gym, zero results, selector auto-navigation and preserved rest
  deadline. Existing 659 browser regression also runs.
- Other relevant Workout 654–661 regressions and release protections
  remain in the isolated scoped gate. All tests run on tracker-dev;
  no GitHub-hosted CI.
- Only after DEV qualification should the established signed,
  DEV-controlled promotion update PROD. No direct PROD work.

## DEV acceptance

Visit Workouts → Rapid Gym Mode during an active routine. Select a
different machine in the dropdown (Go button not required), return,
open the machine directory and filter by machine or gym. Adjust the
load in 2.5-lb increments and reps in 5-rep increments, then restore
to the last recorded values. After a set, use the immediately visible
Next Machine control and verify rest time continues. Confirm each set
and its history through the existing Workout pages.
