# Release 716 — Edit an active Workout and add machines from Gym Mode

**Base Release 715:** `ab70236618df66b8a959c765abf38dbcd59b29d7`
**Branch:** `release/716-active-workout-machine-add`

## User workflow

Rapid Gym Mode now exposes **Edit Workout Sets**, **Edit Routine Order** (for an active saved routine), and a prominent collapsible **Add Machine to Workout** panel.

- **Existing machine, free workout:** select and open it in one action. A machine belongs to this session when a set is actually logged; no phantom sets or synthetic session plans are created.
- **Existing machine, active saved routine:** select and append it to the current saved routine, then open it for immediate logging. This intentionally updates the saved routine for future workouts too, and the UI explicitly says so. Existing session goal snapshots and recorded sets are preserved.
- **New machine:** supply name, type, gym, and optional manufacturer/seat setting without leaving Gym Mode. It is saved in the equipment catalog; if this session is linked to a saved routine, it is appended to that routine in the same database transaction, and opened immediately.
- **Edit current workout:** link to the existing audited set edit/delete controls; editing routine order links to the existing routine editor. Existing set and routine protection logic is reused.

Stale session IDs, unknown equipment IDs, duplicate routine membership, 30-machine routine limit, invalid input and duplicate cataloged name/gym entries are rejected without modifying session sets. All writes use existing authenticated scoped SQLite DB dependency and global CSRF/origin policy.

There is **no migration and no new table**. This release does not change completed-session records or frozen target scores. No actual set is created until the user logs one.

## Qualification

`scripts/tracker-qualify716.sh` ensures exact-commit isolated qualification on tracker-dev: a detached worktree, disposable SQLite, PrivateNetwork systemd context, clean installed baseline and explicit changed-file allowlist. It does not install.

`scripts/tracker-release-scoped716.sh` runs:
- Bash and Python syntax/import checks, plus Release 604 changed-asset preflight in qualify/install runner
- Release 716 direct API/DB tests for free/saved routines, stale submissions, duplicate rejection, new machine creation and preservation of existing sets
- Existing 654/655/659 Workout tests, 668 guidance and 714 routine geometry regression
- Browser catalog/targeted-mode safety registration
- Real mobile Chromium strict-CSRF browser workflow on **HTTP and HTTPS**, using the disposable QA service to create a saved routine, add an existing machine mid-workout, create a new machine mid-workout, and finish

**Not run:** full application regression suite, unrelated food/COA/lab tests, real device manual gym testing. The change is intentionally limited to active-workout UX and corresponding tests. Read-only PROD preflight and signed DEV-controlled deployment require separate explicit PROD authorization.

`scripts/tracker-install716.sh` installs only the same exactly-qualified commit via the existing guarded runner, then the immutable GitHub receipt must confirm success before DEV is considered ready.
