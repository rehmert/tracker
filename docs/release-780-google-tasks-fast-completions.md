# Release 780 — completed Google Tasks import every minute

Baseline: DEV + PROD Release 779, exact SHA `de07ebbbf0e7e2095bdcb2996ce3f4cb776e3205`.

## Change
- Existing full synchronization stays at five-minute intervals (create/update
  open tasks, synchronize schedules, process deletions, and import completions).
- Every intervening minute, a lightweight **completion-only** read checks the
  three existing Tracker Google Tasks lists where open, previously linked tasks
  exist, then imports verified medication/supplement completions.
- Protocol completions still only set a pending-reconciliation status. They
  never consume inventory or fabricate a dose.
- Fast polls never create Google lists/tasks, change titles, delete tasks, or
  make outbound Google mutations.
- The existing nonblocking process lock continues to protect full and fast
  syncs from overlapping across application workers.
- No polling/Google OAuth at all on DEV or when disconnected/disabled, no
  credential changes and no new database tables.
- Only linked Google task IDs are trusted and imported; the existing
  deduplication/audit/recorded timestamp rules remain intact.

## Cadence and limits
The background loop wakes every 60 seconds and runs completion-only polling
on ticks 1–4, full reconciliation on tick 5, repeating. The normal full-sync
cadence is unchanged at 300 seconds, and **Sync now** remains available on PROD.

Each fast poll reads at most the existing linked kinds (up to three task lists),
with pagination if necessary. With one page per list, typical additional
traffic is 3 × 4 × 288 = 3,456 task-list queries/day beyond existing 5-minute
sync; client OAuth refresh adds a token exchange for each fast poll. Google's
published Tasks API courtesy quota is 50,000 queries/day; actual usage
depends on pagination and other clients. No new retries or unbounded concurrency.

## Test scope
Isolated synthetic database/fake Google client tests cover faster import,
idempotency, no Google writes, no list creation, pending protocols/no vial
inventory, disabled/disconnected behavior, lock overlap, error handling and
the exact 1/5-minute background cadence. Existing 769/770/772 completion
and guarded API tests included. DEV install only after scoped qualification;
PROD remains unchanged until explicit approval.
