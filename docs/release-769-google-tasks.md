# Release 769 — Google Tasks for medications, supplements and protocols

Base: completed and both-host installed Release 768, exact SHA
`62a78b4f0b79f2f6762976c1231cab2f5f593f25`.
DEV first; no PROD action or promotion without separate user authorization.

## Scope

- Private Google OAuth 2.0 authorization-code connection with offline access.
  Credentials from /etc/tracker.env only, no OAuth client secrets or refresh
  tokens in GitHub. Google's refresh token stays in the private workspace SQLite
  DB, included in the existing verified SQLite backups.
- Dedicated Tracker DEV/PROD-labelled Medication, Supplement and Protocol
  Google Tasks lists. 14-day rolling forward calendar; 5-minute background
  best-effort poll and user-facing Sync now. No inbound webhook/public Tracker
  endpoint is needed.
- Regimen daily/weekday/interval calendars, active/archived/PRN constraints,
  and active protocol stages, exclusions, anchors, times and end dates.
  Per-schedule exclusions in settings. No medication or dose recommendation.
- Google task IDs and stable Tracker occurrence keys prevent retries from
  creating duplicate tasks, including recovery after a remote insertion
  succeeded but before local transaction commit. Deletions are not recreated.
  Future open tasks are cancelled when schedules change or are excluded;
  historical completed tasks are retained.
- Tasks completed in Google are mapped only to a previously known source.
  Regimen entries are logged once with the selected amount and an audit record;
  Google's actual completion timestamp is preserved in the entry note, and
  the planned date remains the entry date. Existing manual entries are never
  overwritten. Existing taken regimen entries complete the matching task.
- Protocol check-offs are explicitly **pending inventory reconciliation**:
  a Google completion cannot identify an actual source vial, blend, or
  withdrawal, so this release never creates synthetic DoseLogs or deducts
  inventory. The existing /doses flow remains authoritative.
- Google API task due dates are date-only; time is included in the title.
  Undoing a Google completion does not delete a recorded Tracker intake;
  manual correction is required. PRN items are excluded.

## Setup

Register a Google OAuth web application with the Tasks API enabled and the
Google Tasks scope. Configure in the private host environment:

```
TRACKER_GOOGLE_TASKS_CLIENT_ID=<google-client-id>
TRACKER_GOOGLE_TASKS_CLIENT_SECRET=<google-client-secret>
TRACKER_GOOGLE_TASKS_REDIRECT_URI=https://<private-dns-host>/integrations/google-tasks/callback
```

Configure OAuth only on PROD. A Release 770 guard prohibits live Google OAuth,
token refresh, and Tasks API calls on DEV even when copied PROD tokens or
credentials exist. Never commit credentials to GitHub. Without these
values, the integration stays disabled, with no Google API calls.
Testing-mode Google OAuth refresh tokens can expire in seven days; configure
the consent/publishing status appropriately before relying on background sync.

## Database and deployment

Four new additive, isolated SQLAlchemy tables are declared in
`app/google_tasks_models769.py`; no existing tables are altered.
A DEV-only verified SQLite+uploads snapshot using the existing signed
Release 655 backup helper is required BEFORE registering the tables. The
existing guarded DEV runner then performs ordinary impact/source tests,
backup and health checks. A migration-specific reviewed PROD backup/gate is
required before any later promotion. The change does not install dependencies,
edit deployment units or touch user data in GitHub.

All credentialed Google traffic must be tested only after DEV's code has
qualified using synthetic network-free clients. Do not use a real Google
account in automated tests.

## DEV checklist

1. Open /integrations/google-tasks. Verify the disabled configuration state.
2. Do not configure DEV Google credentials. Verify blocked DEV OAuth/API access.
3. Exercise only synthetic mock-backed Tasks clients and isolated datasets.
4. Confirm daily/weekly/interval schedules and staged protocol dates; exclude
   one schedule and ensure only future open tasks are removed.
5. Complete a regimen task from Google Calendar and confirm a single audited
   Tracker intake, then repeat Sync now and check no duplicate intake.
6. Complete a protocol task and confirm pending reconciliation with zero new
   DoseLogs, BlendDoses or inventory adjustment.
7. Log a medication intake in Tracker and confirm the linked Google task
   completes. Verify behavior at Google API unavailability.
8. Explicit approval is required before PROD work.
