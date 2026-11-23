# Release 754 — Private progress JSON export (DEV synthetic first)

## Current capabilities and source mapping

- Weight, resting pulse and BP: vitals readings.
- Completed/in-progress workout sessions, exercise sets and individual
  equipment-based load/volume: Workout 654/667.
- Daily food totals and nutrient completeness: tracker_food_* tables.
- Allowlisted numeric lab observations: lab_reports/lab_results.
- Allowlisted, explicitly *planned* regimen schedules: regimen_*635.

There is no current persistent waist/circumference, body-fat estimate or
goal-weight model in the installed application. Such values are null or
explicitly marked unavailable. Do not infer muscle gain from weight trends.
The current overview and Workout dashboard are the available progress UIs;
there is no unified comprehensive Progress Dashboard data service to reuse.

## Data and authorization

Read-only sqlite3 URI + PRAGMA query_only and an explicit BEGIN transaction.
No ORM serialization, migrations, attachments, IDs related to real persons,
raw notes, source documents, purchases or vendor data. Every category
has a standalone latest/<name>.json file with source, period, units in
field names, completeness, provenance and UTC generation timestamp.

Config is a root-owned 0600 JSON file outside GitHub. Default lab and
medication allowlists are both empty. No PROD read or outbound upload can
run unless the local source is PROD, the selected file is the exact
configured DB, and an administrator explicitly enables prod_approved=true.
Do not enable this on PROD during Release 754 DEV verification.

The exporter uses a repository-scoped GitHub token from a separate 0600
root-owned file. Check private=true, visibility=private, exact repository
name and default branch before publishing and once before committing.
Upload changed dataset files in one fast-forward Git tree commit. Skip
unchanged snapshots by semantic digest, ignoring generated_at_utc.
Use a separate root-only working directory. Never print token or JSON.
No inbound listener or additional always-on service.

Git history retains replaced health data; this integration does not
rewrite history. Keep retention windows bounded to 365 days by default.
Revocation of repo access and token stops future uploads; erasure of
historical data requires a separately reviewed repository lifecycle plan.

## DEV acceptance and external prerequisites

1. Install / qualify Release 754 to DEV. Its focused test suite creates
   synthetic SQLite fixtures, never reads actual DEV health records,
   verifies no mutation and checks 403/public-repo rejection.
2. The destination private repo must be created by the repository owner.
   Our current ChatGPT GitHub connector cannot create GitHub repositories,
   and it does not currently have access to tracker-progress-data.
3. Once created, set repo visibility PRIVATE and initialize main.
   Authorize the ChatGPT GitHub connector for that repository. Configure
   a fine-grained token scoped only to its Contents read/write.
4. Run the CLI in synthetic source mode with TRACKER_INSTANCE=DEV and a
   *synthetic SQLite file*, then --sync. Verify the private repo manifest
   and individual JSON data can be read through ChatGPT's connector.
5. Only after separate explicit approval may the administrator install
   the supplied systemd templates under scripts/systemd/ on PROD, create
   root-only config + token, change prod_approved to true, and enable the
   nightly timer. Do NOT enable during DEV development.

## Nightly service and manual Export Now

Use scripts/systemd/tracker-progress-export754.{service,timer} as reviewed
source templates. They are never installed merely by deploying application
source. The timer runs at about 03:10 local with a bounded random delay;
a failed run never changes Tracker DB or blocks normal web requests.
"Export Now" is a manual invocation of the service or the same CLI.
Local status.json records the last successful snapshot. A failed upload
returns nonzero and prints a sanitized error code only.

## Qualification

Only change-scoped synthetic tests; source and systemd templates require
review before enabling on PROD. No live data or credentials in GitHub
source, release artifacts, logs or receipts. Keep strict CSRF unchanged.

DEV synthetic fixture generation (root-only):
`TRACKER_INSTANCE=DEV /opt/tracker/.venv/bin/python /opt/tracker/scripts/tracker_progress_fixture754.py /var/lib/tracker-progress-export/fixture.db`
The exporter checks a separate synthetic-marker table before reading a DEV fixture. A copied live database without that marker is rejected.
