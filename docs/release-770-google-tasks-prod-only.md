# Release 770 — permanently block live Google Tasks on DEV

Base: DEV-installed Release 769, exact SHA
`9f3e1154f30d5b2711957f51c675006f666d3440`.

## Behavior
- Every real network entry point (Google Tasks HTTP, OAuth token exchange, Tasks
  client construction and OAuth authorization URL) fails closed unless the
  trusted local Tracker instance label is exactly PROD.
- DEV suppresses OAuth configuration even if `/etc/tracker.env` contains
  credentials or copied PROD refresh tokens. DEV connection, callback and
  Sync now routes explicitly deny. DEV settings display a read-only mock-only
  notice; no Connect Google button is shown.
- Existing synthetic clients and isolated test fixtures still exercise
  projection, deduplication, completion reconciliation and inventory safety.
- Do not connect a DEV Google account; no live DEV Google credentials needed.
- No schema/dependency/systemd changes. Release 769's four additive tables
  already exist on DEV. PROD is still on 768; a later PROD catch-up must
  explicitly review these new tables and perform verified backup before any
  source deployment.
- Exact SHA qualification -> DEV installation. Do not promote or deploy PROD
  without the user's explicit authorization.

## Tests
New negative tests cover DEV, unconfigured, TEST/STAGING labels; accidental
credentials; copied PROD refresh tokens; direct instantiated client; browser
connection/callback/manual-sync routes; and unaffected PROD OAuth URL generation.
Use the existing Release 769 mock-based full integration tests and targeted
regimen, tablet, controller regressions. No Google network in tests.
