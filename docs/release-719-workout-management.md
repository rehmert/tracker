# Release 719 — Delete workouts and reveal paginated dashboard history

**DEV baseline:** Release 718, `18a1bf7a6171ef1eeef80e4588851cd500031cb4`.
**Release branch:** `release/719-workout-delete-dashboard-pagination`.

## User workflow

An accidentally started workout can be deleted from:
- **Workouts**: the in-progress workout box, or its Recent Workouts row.
- **Rapid Gym Mode**: **Delete Accidental Workout**, opening the session history with the deletion control.
- **Workout Session History** and **Session Review**: **Delete Workout**.

The deletion form is collapsed by default. It identifies the specific workout start time, requires a reason (defaults to *Started by mistake*), and requires a separate explicit checkbox before **Delete Entire Workout**. On success return to Workouts with a message. Deletion cannot be reversed through the UI; an immutable private audit snapshot is retained.

The Overview **Workout Activity → Recent Workouts** section is also collapsed initially, and uses native HTML disclosure. Expanding reveals the newest **10 workouts**. **Previous 10** and **Next 10** navigate in groups of 10, show **Page X of Y**, and preserve expansion on server-rendered navigation. Last-page sizes may be less than ten. Page parameter is bounded and clamped. Sessions are ordered by actual start timestamp then stable ID descending, and include completed, incomplete and zero-set sessions for deletion visibility. Frequency KPIs **remain restricted** to real completed workouts containing sets, as before.

## Audit / DB integrity

- Authenticated scoped SQLite dependency and existing CSRF/origin guard. Exact session ID and original started-at hidden value prevent accidental stale/wrong-session deletion. Confirm and reason validations fail closed.
- **No schema migration**. Before deletion, a single durable private `ChangeAudit` snapshot stores start/completion times, original sets (weight/reps/effort/type/equipment/timestamp), the prior audited corrections, frozen session goals, associated routine ID, and offline-sync receipts, with user explanation. Earlier ChangeAudit entries are not removed.
- In the same atomic DB transaction, delete FK-restricted correction and offline receipt records and session-specific targets/associations before recorded sets and the session. The machine catalog and reusable routine definition remain.
- Offline-sync UUID tombstones are retained in private ChangeAudit records. An old offline UUID cannot create a new set after deletion, even if SQLite later reuses the session ID. Replays are rejected on mismatched payloads; matching deleted actions are acknowledged as deleted. Other sessions and records are unaffected.
- Historical charts/totals read actual surviving sets and automatically exclude deleted sessions.

## Isolated qualification

Exact-commit detached-source QA based on clean Release 718 DEV. Restricted changed-path allowlist, impact-preflight 604, isolated disposable DB, PrivateNetwork systemd. Scoped tests cover empty active deletion, completed deletion with corrections/routine/frozen goals/offline receipt, failed confirmations and stale IDs, paginated 23-session fixture including empty/incomplete, dashboard disclosure HTTP, existing workout 654/657/663/668 regressions and dashboard UI/CSS order contracts. Signed mobile Chromium HTTP+HTTPS exercises both session types and initial hidden dashboard history.

No routine full application suite. Once qualification passes, guarded DEV installation of the exact commit only. **PROD requires separate explicit authorization**, and existing PROD is at Release 715, so DEV 716–719 changes must be promoted through the approved controlled process.
