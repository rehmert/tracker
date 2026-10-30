# Stage 14 — Purchase and supply-use replay protection

Purchase-header creation and supply usage now acquire a SQLite write reservation before reading or changing inventory, and accept durable per-form UUID submission identifiers. A successfully committed identifier is recorded in `inventory_submissions` in the same transaction as the mutation. Identical retries are treated as replays; conflicting reuse is rejected. Supply usage also rejects non-finite values.

Scope: purchase header creation and `/supplies/{sid}/use` only. Existing legacy clients without tokens remain compatible but are not replay-protected. Other purchase-item creation and editing flows remain to be covered. No new migration beyond the Stage 13 table.
