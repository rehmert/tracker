# Stage 13 — Durable inventory request replay protection

Creates `inventory_submissions` automatically on application startup via SQLAlchemy metadata.create_all. Existing tables are not altered. A unique UUID per rendered form is saved in the same transaction as the inventory operation. Replays of committed requests are detected before mutation, while failed submissions can be retried. Reusing a token with different input is rejected.

Covered: dose creation, blend creation, blend draws/waste, supply reconciliation. This does not yet cover all inventory mutations. Tokens are bound to form payloads; a fresh form must be loaded for a second legitimate action.

This is not an authentication or CSRF mechanism. Deployment requires a one-time new table creation (automatic startup).
