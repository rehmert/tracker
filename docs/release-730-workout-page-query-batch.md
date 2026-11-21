# Release 730 — Bounded Workout page SQL reads

**Pending application base:** verified DEV Release 729, `d2597c5bfab3c76e1701a42af00ab5ce41553818`.

## Measured mechanism and change

The Workout equipment page previously executed a `SELECT` for the most
recent WorkoutSet for **each** machine. The route therefore performed
O(number of machines) SQL reads. Its active-session count dictionary
also rescanned all recorded sets for each machine.

This release ranks WorkoutSet rows using one SQL `row_number()` window
partitioned by equipment, ordered by `performed_at DESC, id DESC`, and
selects only rank-one rows. That preserves the earlier tie-break and
includes sets from active workouts just as before. Machines without
a set remain keyed to `None`, as the existing Jinja template expects.
The active-set count uses a Counter for linear-time accumulation.

## Scope and validation

- Only `app/routers/workouts654.py` is changed in application code.
- No schema, migration, dependencies, endpoints, auth or write changes.
- New disposable SQLite tests measure SELECT counts at 1, 5 and 40
  machines, confirm latest-set tie-breaking, empty machines, active
  workout counts and no changes to the read-only route's write behavior.
- Existing Workout route and dashboard regressions are included.
- Exact changed-path allowlist, syntax checks, impact preflight,
  detached worktree, disposable data and private-network QA.
- Full regression suite is intentionally not requested.

## Release ordering

**Hold isolated qualification and DEV install until separately approved
Release 729 PROD promotion is verified.** Keeping DEV installed at 729
allows the existing signed native PROD promotion to validate the exact
installed DEV SHA; installing 730 prematurely would break that guarantee.

730 qualification and DEV installation may proceed after PROD 729
verification. PROD 730 requires its own explicit authorization.
Once this performance scope is accepted, proceed with dependency
reproducibility and strict CSRF in that requested order.
