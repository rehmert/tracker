# Release 674 — Integrated Productivity

Baseline: Release 673 at `97ba851c29e9f9d06d16577d60716fd342feeaf8`.
Candidate branch: `release/674-integrated-productivity`.
One integrated code-only release; **no CSRF-related changes**.

## Delivered capabilities

**Daily command center**: The existing /mobile Today route now includes a
compact, non-mutating snapshot of reported Food Journal calorie totals and
record count, today's started workouts and set count, and vial date attention.
Unknown nutrition is never represented as a complete total; source coverage
is clearly labeled. Food data is optional and restricted by the existing
Food storage authorization. Secondary workspaces never read administrator
food records.

**Contextual quick actions**: Today links directly to recording food,
workout sets, readings, the latest workout review and inventory date review.
Existing Food and Workout repeat actions continue to work unchanged.
Links navigate to existing controlled workflows rather than silently writing.

**Data Quality dashboard**: /data-quality gathers incomplete COA
metadata/documentation, purchases lacking recorded inventory, machines
without QR mapping, and used saved foods with absent core nutrient values.
Every finding links to the relevant correction workflow. This page performs
read-only checks and is independent of the existing detailed FEFO/inventory
data quality view. Food is excluded if the existing guard denies access.
The page renders the first 100 issues, with full counts for other
uncapped categories; Food assesses up to 1,000 recently used products.

**Audited Undo and recovery**: On completed-workout correction history,
the most recent correction for each set (if not itself a reversal) has an
Undo control. The handler rejects unrelated, incomplete, already-undone,
stale, or superseded corrections, restores recorded values and set type,
and writes a second immutable correction audit row. Normal historical
manual correction remains available. No direct deletion or silent data
restoration is offered for Food, inventory, or other unsupported records.

**Workout progression**: Rapid Gym displays a transparent optional
next-session suggestion derived solely from the most recent completed
session for that machine. It excludes warmup sets. A modest load increase
is suggested only when the latest three working sets share the same load
and meet the configured rep target, or an explicitly labeled fallback of
8 repetitions. Otherwise it suggests repeating the current load. The
button only fills weight/reps inputs; it never saves a set, changes a
routine goal, or estimates cross-machine equivalence.

## Safety and compatibility

- All new workout read/writes use the existing authenticated scoped DB.
- Food storage is accessed only through the existing per-request authorization.
- No new database tables, migration, changes to dependencies, or CSRF modules.
- Former saved-food editing, workout recording, and correction endpoints
  remain unchanged. Only new routes, rendering and optional read-only
  helpers are added.
- Corrections remain auditable. UI uses ordinary existing form actions.
- The suggestion is training guidance only, not an individualized medical
  or rehabilitation recommendation; it never changes data automatically.

## Qualification

`scripts/tracker-preview674.sh` creates an isolated non-installing DEV
worktree and runs `scripts/tracker-release-scoped674.sh`: syntax checks,
Jinja parsing, focused tests for Undo and stale guards, progression without
writes, read-only dashboards, Today routes, historical workout corrections,
Rapid Gym/offline actions, saved food edits, and shared mobile navigation.
No full Tracker suite on each release.

After preview passes, a separate readiness marker will authorize
`scripts/tracker-release674.sh` for pinned DEV qualification and guarded
signed promotion to PROD, with the same focused test gate on PROD.
