# Release 735 — Guarded production catch-up from 727 through 734

## Objective

PROD remains at Release 727; DEV already verified Releases 729–734.
Release 728 is a DEV-only release-controller upgrade and is **not** an
application PROD deployment. This release is a deployment-safety gate,
not a new application feature.

## Why the existing 734 PROD path is blocked

Release 731 added two tablet-dose tables in `app/models.py`. The
current signed PROD streamer only supplies reviewed migration flags
for certain historical release numbers (not 734), so directly promoting
734 from installed 727 would push GitHub main and then fail at the
database schema gate. No such unsafe promotion is allowed.

## Reviewed one-time catch-up

- Verify exact installed PROD base `3718936aedfcb1b8fe243c86fe6fc7e06a7a41d2`
  (Release 727) and immutable ancestry through all six DEV releases.
- Verify the old ORM schema is unchanged through Release 730.
- Reuse immutable Release 731's original standalone additive-schema
  review against the original Release 731 commit; only the two reviewed
  one-to-one tablet tables may be added.
- Verify `app/models.py` is unchanged after 731, and no other schema,
  deployment or dependency files changed since installed PROD 727.
- Signed DEV runner and remote streamer accept a PROD-only,
  release-specific `--reviewed-catchup-735 --db-migration` combination.
  It cannot be used from DEV or any other PROD starting release.
- PROD runs isolated cross-release focused DB, API, Jinja and Chromium
  regressions, then strict live attachment-integrity checks, verified
  SQLite/upload backup, and isolated restore verification **before**
  any live checkout changes. All original signed-approval and
  rollback paths remain in place.
- Final target contains all app changes from Releases 729–734.

## Release protocol

1. Qualify exact Release 735 SHA in private-network disposable DEV worker.
2. Guarded install on DEV, with immutable `dev_install` receipt.
3. Queue signed PROD `prod_preflight` with **actual PROD 727 SHA**
   as request base, chained to the DEV installation receipt.
4. Queue `prod_deploy` only after a passed immutable preflight receipt
   for exactly the same target, base and branch.
5. Independently verify PROD service active and PROD/GitHub main
   equal the exact qualified target SHA. Never repeat a possibly
   completed stage; stop on unknown or partially promoted state.

No secrets, database archives, raw logs, medical records or private
release approvals are committed to GitHub. Full suite is not run;
cross-release integration regressions and the standard isolated
production deployment gates are the specific qualification scope.
