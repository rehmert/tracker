# Stage 15 — Purchased inventory replay protection

Extends Stage 13/14 durable idempotency to purchase detail forms: purchased vials (including kits), BAC water inventory, and supplies/pills. Each form receives a fresh UUID when the purchase detail page renders. Operations acquire a SQLite write reservation before checking token and inventory; successful mutations and their audit rows are committed with the token. Identical retries do not create duplicate inventory or audit records; token reuse with different inputs is rejected. Legacy clients without a token still work but do not receive replay protection.

No new database tables or migrations beyond the Stage 13 `inventory_submissions` table. Scope does not include editing/deleting purchased items. Browser and concurrent-request stress testing remain necessary.
