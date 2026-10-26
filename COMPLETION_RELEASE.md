# Tracker v2.1 — Remaining-phase completion pass

## Implemented
- Vial lifecycle fields: received, first punctured, first administered, user-documented beyond-use date, closed date, and storage notes. Existing status and reconstitution fields remain. All dates are optional; no medical beyond-use period is inferred.
- Additive SQLite schema migration for the lifecycle columns; existing rows remain unchanged.
- Mobile form improvements and an installable web-app manifest. This remains an online-only app: no service worker, offline cache, or background synchronization.

## Important limitations
- Full Alembic adoption, comprehensive audit of every CRUD operation, new dashboard widgets, and advanced search have NOT been implemented in this package. Existing schema migration logic is retained to avoid unverified conversion of older production databases.
- A web manifest alone does not guarantee installation on every browser; serving over HTTPS is generally required for home-screen installation.
- These are data-recordkeeping fields, not storage or medical recommendations.

## Deployment
1. Back up and verify your existing database and uploads.
2. Preserve .env, data/, and uploads while deploying this package.
3. Restart tracker.service and hard refresh your browser.
4. Verify vial lifecycle editing on a noncritical vial before routine use.
- Lifecycle changes now append before/after records to the existing change_audit table.
- Data Integrity now flags inconsistent lifecycle dates, passed documented beyond-use dates, and active vials with closure dates.
- Validation: 93 automated tests passed (91 prior plus 2 lifecycle migration tests).
