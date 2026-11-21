# Release 739 — Workout & Food MACD + mobile UI/CSS consolidation

Baseline: verified Release 738 DEV/PROD and GitHub main SHA de867eee93004534fa822e7250deda75d0976558.

One combined release advances the MACD and mobile UX/CSS workstreams without schema changes, dependency upgrades or global styling rewrites.

## Workout routines — Add, Move, Change, Delete
- Preserve existing Create, Duplicate, machine Add/Replace, Move up/down, routine Start, goals and schedules.
- Expose Edit routine in saved-routine list and detail. The native disclosure opens prefilled name; server validates 1–120 characters and writes a ChangeAudit snapshot for real edits.
- Expose Delete routine only if zero active/completed sessions reference that routine. Even forged POST fails when any history exists.
- An explicit confirmed Delete removes only unused routine plans, grouping members/groups, goals, equipment membership, schedule and rest configuration in one FK-safe transaction. Retain equipment, recorded sessions and sets; refuse corrupt cross-routine group membership; write private audit.
- All controls native GET links or POST forms, 44px+ and keyboard accessible.

## Saved Food — Change and safe Delete
- Existing Edit retains immutable saved record ID and stale-version protection.
- Add visible Delete Saved Food beside Save/Cancel in established mobile action row; independent native POST form uses HTML form target to avoid nesting.
- Require the same SHA-256 record version and explicit delete confirmation.
- Deletion forbidden if recorded meal entries or meal templates reference the product; UI shows reason, forged POST returns 409. Any favorite association is removed atomically when an otherwise unreferenced product is deleted. An unexpected FK conflict blocks without mutation.
- Other foods, logged meals, templates, favorites and nutrition totals are retained.

## Mobile/CSS consolidation
- New canonical tracker-workout-routines739.css begins with the exact old tracker-workouts655.css followed by tracker-workout-routine-alignment714.css. Scoped 739 management styles follow. Routine detail loads one stylesheet instead of two; list uses the same canonical routine stylesheet.
- Legacy originals remain in Git for historical regression, with their CSS rule order preserved.
- Existing tracker-saved-food-actions702.css is updated in place for the new Delete action, retaining sticky Save/Cancel on mobile and keyboard/focus behavior.
- Remove duplicate routine detail navigation; use one grouped, styled link row.

## QA, promotion and boundaries
- Exact-SHA allowlist, guarded isolated DEV worktree and private SQLite, root PrivateNetwork worker, Release 604 impact gate.
- Focused Python/Jinja shell checks, real HTTP/API tests, FK-ON SQLite negatives, and Chromium at 320/390/760/1024 in light/dark. Run original 655, 669, 702, 714 and relevant 738 regressions. No full suite for targeted scope.
- Verify immutable qualification and DEV installation receipts. PROD only after separate explicit instruction.
- No secrets, medical data, DB backups or raw logs in GitHub.
- Remaining app-wide MACD/CSS cleanup (Notes, supplies, equipment with historical sets, additional legacy CSS) requires separately guarded future work and must not be advertised as complete.
