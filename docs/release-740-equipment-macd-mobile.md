# Release 740 — Workout Equipment MACD + mobile CSS consolidation

Baseline: exact Release 739 DEV/PROD/main SHA
a0bd6f6f1d0056e16acb6b134ed4bc21fe6ce48f.

One scoped release continues issue #56 (MACD) and issue #54 (mobile
UX/styles) on the high-use Workout equipment workflow. No schema change.

## Equipment MACD
- Existing **Add Equipment** and **Machine Setup** controls remain unchanged.
- Expose **Edit equipment** as a native disclosure with prefilled machine
  name, gym, manufacturer and model. Preserve kind, existing QR mapping,
  seat settings, setup notes, equipment ID, logged sets and routine links.
- Reject blank/oversized names, invalid metadata and stale edit requests.
  Use an optimistic SHA-256 version of only the identifying fields and a
  private ChangeAudit before/after snapshot for actual edits.
- Expose **Delete equipment** alongside Edit when a machine has no
  recorded sets, saved routine memberships or frozen workout session targets.
  Use three grouped queries for counts, not a per-machine query loop.
- Show a disabled Delete control and specific association counts when
  deletion is forbidden. The POST independently rechecks all associations
  and a precise record version; reject forged or stale requests.
- A confirmed unused Delete retains equipment ID in a private audit
  snapshot, removes only interpretation metadata dependent on that machine,
  and deletes the equipment atomically with database FK constraints enabled.
  Never erase historic sets, routines, workout targets or other equipment.
- Move is relevant for routine exercise order, not the standalone equipment
  catalog; keep existing routine move controls.

## Mobile UX / CSS
- Existing adjacent tracker-workouts654.css and
  tracker-workouts655.css on Workouts home are concatenated in original rule
  order into tracker-workout-equipment740.css; scoped 740 action styles follow.
- Workouts home now issues one asset request in place of those two. Other
  pages retain their original stylesheet references and historic coverage.
- Explicit 44px+ actionable targets, native disclosure marker, keyboard
  focus, narrow-phone layout, light/dark theme and no content overflow.
- No global CSS replacement, JavaScript rewrite or changes to workout
  logging, rest timers or the active workout flow.

## QA + guarded DEV-only promotion
- Release 739 exact baseline, 15-minute-independent exact release SHA,
  clean installed DEV source and Git ancestry check.
- Release 604 read-only asset impact preflight and 740 changed-file allowlist.
- PrivateNetwork systemd isolated detached worktree, disposable SQLite
  with foreign keys enforced and no production data.
- Focused 740 API/DB/browser tests: valid/invalid/stale edits, retained QR
  and settings, 3 history dependency scenarios, protected Delete, audit,
  existing logging, original CSS cascade parity and Chromium 320/390/760/1024
  in light/dark; selected preexisting Workout 654/655, 714, 739 regressions.
- Shell/Python/Jinja syntax, limited integration smoke, no whole-app suite.
  Publish exact test counts and immutable qualification/install receipts.
- DEV install only after qualification; PROD preflight and promotion require
  a separate explicit operator instruction. No raw logs, private data or
  backups committed to GitHub.

## Remaining MACD
Supplies/accounting, Notes, additional equipment ownership/custody, and
further shared CSS reduction remain incremental work. Do not claim the
entire app is MACD complete.
