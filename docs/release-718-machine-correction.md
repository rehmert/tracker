# Release 718 — Correct the machine in a completed workout

**DEV baseline:** Release 717, exact SHA `0893bde49014616bc878b0b142ad5bfe1bbf8f16`
**Release branch:** `release/718-completed-machine-correction`

## Use case

A user finishes their gym workout, then realizes sets were logged under the wrong machine. A completed session must remain completed, but its actual recorded equipment assignments need correction. The user may have logged one mistaken set or all sets against the wrong machine.

On **Workouts → Recent Workouts → Edit Workout**, the completed-session editor now offers:
- **Wrong Machine for Several Sets?** Expands one section per machine with recorded sets, each with a catalog machine selector, required reason, confirmation and **Move All N Sets** button. The request includes exactly the set IDs shown on page as a stale-state guard.
- Under **Edit Set / Change Machine / Remove**, **Correct Recorded Machine** offers a machine selector and **Save Correct Machine**. Correcting this one set does not move its neighbors, and includes a stale previous-machine check.
- **Change History** shows immutable before/after machine identities, original set identifiers and the explanation, including after the set has later been removed.

Neither action requires reopening the workout. Recorded set count, reps, weights, timestamps and session completion do not change. Machine-specific totals, progress and exports use the updated actual records, not a fabricated session snapshot. Existing frozen training goals are not rewritten.

## Integrity / audit

- No schema migration. Uses existing `ChangeAudit`, one event per changed set, committed in the same scoped SQLite transaction as `equipment_id` updates. Records old/new machine IDs and names, session ID, original logged timestamp, and reason.
- Both routes reject incomplete sessions, nonexistent destination machines, no-op moves, invalid reasons, and mismatch of existing session/set identity.
- Bulk moves require explicit confirmation and the exact original set IDs, guarding stale forms and changing set membership. All set assignments and all audit entries commit together or not at all.
- The existing numeric correction and removal/undo routes are unchanged.
- Global CSRF and authenticated scoped DB gates continue to protect form actions.

## Qualification

Exact-SHA isolated QA through `scripts/tracker-qualify718.sh` verifies a clean installed Release 717 DEV base, bounded changed-file allowlist, detached worktree, PrivateNetwork, temporary SQLite and impact-preflight. Scoped Python test groups cover one-set and bulk machine changes, audit before/after, stale/invalid/missing requests, completed-only protections and unchanged sets plus existing historical correction/removal regressions.

The dedicated mobile Chromium browser test exercises signed form submissions under HTTP and HTTPS: log 3 sets to the wrong machine, finish, bulk move all 3, then individually reassign one back, verify completed state and reviewed totals. No full app-wide suite.

After a passing exact qualification receipt, guarded DEV installation via `scripts/tracker-install718.sh` may proceed. PROD is unchanged until separate authorization, then guarded DEV-controlled promotion. The preexisting PROD baseline is Release 715, so Releases 716 and 717 would also need to be promoted as prerequisites.
