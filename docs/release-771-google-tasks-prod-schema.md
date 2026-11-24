# Release 771 — strict PROD 768 Google Tasks schema catch-up

DEV baseline: exact installed Release 770,
`a236ef996c725a231b6420ebf41dd63bf506e8bc`.
PROD remains Release 768,
`62a78b4f0b79f2f6762976c1231cab2f5f593f25`.

## Why this release exists
The Google Tasks integration added four independent model tables in 769.
The historical guarded PROD runner does not automatically recognize
`app/google_tasks_models769.py` as a migration, though it does perform
ordinary backups. Release 771 adds an explicit schema review and VERIFIED
database+attachments backup before source installation. It does **not** change
the DEV-qualified application code or connect DEV to Google.

The pinned PROD-side guard fails closed unless:
- PROD is the expected clean, running 768 checkout;
- target is a descendant of DEV-qualified 770; every application file from
  768 to target equals the exact code independently qualified and installed on
  DEV 770, and only the expected 10 app paths changed;
- the existing models/migrations/database modules and dependencies are untouched;
- the new model module declares exactly the four expected tables, app/main
  registers them, and the mandatory PROD-only Google client guard remains;
- the existing database passes SQLite integrity and FK checks and does not
  already have the new tables;
- existing attachment hashes pass and a complete private database/attachment
  snapshot passes checksums and isolated restore validation.

The backup is kept private on PROD with a 10-archive retention cap, alongside
the standard guarded runner backup. Existing user data and credentials are not
uploaded to GitHub. A failed guard aborts before source installation.

## Stages
Exact SHA offline QA, guarded DEV installation, then separate approved PROD
preflight and DEV-controlled production deployment. No live DEV Google API
calls under any circumstances. PROD OAuth remains unconfigured until separately
set on PROD after deployment.

## Tests
Synthetic schema/SQLite/relative-path/negative-host checks plus prior
769 mock sync, 770 DEV denial, existing 767 relative-path safeguard and
release-controller regressions. No full suite, internet or live Google account.
