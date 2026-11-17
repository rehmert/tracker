# Release 668 — Advanced Workout Programs & Data Operations

**Baseline (qualified DEV and PROD):** Release 667
`9baa03fb521573ba17ec1853fb85d40a22895336`.

**Source branch:** `release/668-advanced-workout`.

Release 668 deliberately combines **all remaining improvements** from the
workout roadmap into one candidate and one guarded DEV/PROD release:
D, E, F2, F3, F5, F6, F7, F8, F9, F10, F12.

## Bundled capabilities

| ID | Scope |
|---|---|
| D | Recurring weekly program/split scheduling linked to reusable saved routines, displayed in calendar |
| E | Retrospective program and set-goal adherence, recorded volume, exact-rep PRs, training frequency and effort trends |
| F2 | Optional exercise group labels for Supersets/Circuits, with direct gym-floor peer navigation |
| F3 | Explicit session-only alternate-machine selection, locked after original/alternate logging; no machine-equivalent strength inference |
| F5 | Copy saved routines (including 667 goals and rest, 668 groups) or make a new *draft routine* from actual completed-session sets |
| F6 | Audit-preserving edits/deletes of completed sets with reason and before/after JSON; no revisions to frozen 667 session targets |
| F7 | Per-equipment recorded-load convention: total/stack, per-hand, or added external load; no retroactive numerical conversion |
| F8 | Export completed actual workouts to RFC 4180 CSV and import bounded, validated Tracker CSV into *new* completed sessions in one transaction |
| F9 | Offline set queue in an already-open Rapid Gym tab, with idempotent UUID receipts, session matching, reconnect replay and visible pending/synced status |
| F10 | Descriptive insights based on actual sessions, matched-rep records, entered effort and frozen goals, not recommendations or 1RM inference |
| F12 | Upcoming weekly workouts and a recent qualifying working-set goal summary on the existing customizable home Workout dashboard |

## Seven additive tables

`app/workout_models668.py` declares exactly these **new** tables:

1. `workout_training_days668` (weekday + routine, unique slot)
2. `workout_routine_groups668` (routine item → superset/circuit label)
3. `workout_session_substitutions668` (session/original → alternate equipment)
4. `workout_set_audit668` (append-only prior/after values and a reason)
5. `workout_load_semantics668` (per-machine recording convention)
6. `workout_import_receipts668` (content digest for duplicate CSV detection)
7. `workout_offline_receipts668` (idempotent UUID → committed actual set ID, retained as a tombstone even after set deletion)

The existing `workout_models654.py`, `workout_models655.py`, and
`workout_models667.py` files are unchanged; no old actual sets are
backfilled, deleted or reinterpreted by schema initialization.

## Workout program / scheduling

Visit `/workouts/programs` to assign saved routines to recurring
Monday–Sunday slots. A week can have several routines on the same day.
Use the existing `/workouts/calendar` view to see planned routines
**separately** from actual completed workout counts.

Visit an existing saved routine to edit group labels. Superset/Circuit
group members appear in Rapid Gym Mode as links. Group labels do not
automatically create sets or prescribe rest; existing set logging is
unchanged. A saved routine can be duplicated into a draft with its
previously defined targets, notes, rest settings and group labels.

## Substitutions

In an active saved routine, select a different cataloged machine
outside the routine in Rapid Gym. The chosen alternate is linked to
that session and original exercise only. It cannot be changed after
sets were recorded on the original or alternate. A replacement load
is **not** counted as equivalent to the original planned load/goal.
Frozen original session targets are never modified.

## Historical corrections

Open a completed session's recorded-set history, choose to correct or
delete an actual set, and supply an 8–300-character reason. The
existing active-session correction endpoint remains unchanged.
Both actions atomically record `workout_set_audit668` with
original set ID, previous values, new values/deletion marker, reason
and timestamp. Deleted set ID intentionally stays in the audit row
as an integer (not a cascade-prone FK), so the audit survives
the actual set deletion. Active sessions cannot be changed via
this endpoint; sets from unrelated sessions are rejected.

## Load semantics

On each machine's Progress screen select total/stack/bar (as entered),
per-hand, or added external bodyweight load. This sets a label
rather than multiplying recorded pounds by 2 or making up bodyweight.
Original 654 volume/analytics is still **sum of entered lb × reps**;
new Insights shows the per-machine convention when summarizing sessions.

## CSV round-trip

`/workouts/data` provides the server-generated CSV export and a
local file preview/import form. Header order:
`session_key,session_started,session_completed,equipment_id,weight_lb,reps,effort,set_type,performed_at`.
Import maximum: 160 KB, 500 sets, 50 completed same-day workouts.
Only existing scoped equipment IDs are accepted. Timestamps must
be valid naive local datetimes within the same completed workout, up
to 12 hours; no future sessions. Weight/reps/effort/type are validated
against the same ranges as normal set entry. Unknown equipment,
duplicates, malformed rows, or an existing identical workout
window abort **the entire batch without writes**.
Imported batches are marked with a SHA-256 digest to reject
exact repeated imports. Import does not recreate or rewrite
frozen historical 667 goals.

## Offline queuing — safety and limitations

Rapid Gym Mode now offers **Queue Set Offline** and **Sync Queued Sets**.
When the browser reports offline, the existing Save Set form queues
instead of attempting an online POST. Queued sets are stored locally
in this browser, tied to the originating active session, and shown
as **pending — not saved**.

When reconnected, the client POSTs each queued entry to
`/workouts/offline/sync` using existing same-origin credentials,
origin/CSRF protection, and a cryptographic UUID. The server
requires that the original session is *still* active, the equipment
exists, and all values are valid; the set and UUID receipt are
committed in **one SQLite transaction**. A repeated UUID returns
the original set ID and is never logged twice. Failed sync/login
or ended-session mismatch retains the queue for manual review.

**Important limitations:** this is an offline **already-open-tab**
queue, not a universal offline-reloading PWA. Logging must begin
while the Tracker workout page is open. Browser localStorage can be
evicted or cleared, or exposed in a shared browser profile; it is
not a server backup. Don't log out, finish the workout or switch
accounts with unsynced sets. Confirm a zero pending count before
finishing; manual recovery may be necessary if the session has
ended. This behavior is deliberately conservative to avoid
silently merging pending data into a different workout.

## Testing & release safeguards

- Explicit schema classification and `--db-migration --reviewed-workout-668`
  are required by both DEV and the signed PROD wrapper.
- New-table constraints, unchanged old models, exact-source blob
  review, unmodified authentication/CSRF/DB core, and exact branch
  restrictions are enforced before a migration backup or live write.
- DEV must pass Release 668 backend tests with disposable, isolated
  SQLite DBs, all 654–667 workout regressions, browser/mobile tests,
  syntax, template checks, source impact preflight, and existing
  guarded release-runner checks.
- Browser tests verify pending-versus-synced display, duplicate-safe
  replay, session mismatch retention, mobile widths and no horizontal
  overflow.
- PROD remains on Release 667 until the new exact SHA is DEV
  qualified and explicitly signed/promoted.
- `scripts/tracker-workout-dev668.sh` is the pinned DEV-only schema
  deployment script, extracted from the exact candidate Git commit.
- `scripts/tracker-workout-promote668.sh` provides a read-only
  signed-promotion preflight by default and requires explicit
  `--execute` after DEV qualification to promote to PROD. It reuses
  `tracker_promote568.py` and never bypasses approval signatures.
