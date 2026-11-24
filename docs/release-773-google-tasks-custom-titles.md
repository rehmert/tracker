# Release 773 — custom Google Tasks titles

DEV/PROD baseline: Release 772 at
`47642b465b1cb98f40aab2ce68c6a7526394298d`.

## User behavior
A medication or supplement **schedule**, or an individual protocol **item**,
can have a short optional Google Tasks title edited directly beside its
Include/Exclude setting at `/integrations/google-tasks`. The Google title
applies to every projected occurrence of that schedule/item. If the field is
blank, Tracker retains its original automatic title. Save a blank title to
restore the default.

Examples:
- Tracker medication name "Synthetic Long Medication", amount "1 tablet":
  optional Google title "Medicine" -> `07:30 · Medicine`.
- Tracker supplement "Synthetic Vitamin D3 + K2", amount "1 capsule":
  custom "Vitamin D" -> `07:30 · Vitamin D`.
- Active protocol item "Synthetic Somatropin", 1.5 mg: custom "HGH" ->
  `07:00 · HGH`.

Tracker names, schedule times, amounts, and inventory are never modified.
Google due dates remain date-only. Custom-title tasks include the full
Tracker name and scheduled amount in the Google notes field, along with
existing linkage and protocol reconciliation instructions.

The existing Google Tasks occurrence keys and remote task IDs do not change.
The next sync patches **open** tasks in place; completed historical tasks are
preserved. Title changes never create new Google tasks or duplicate logged
administrations. Previously hidden inactive/what-if protocols stay hidden and
remain ineligible for synchronization.

## Persistence and security
An independent additive table `google_tasks_titles773` associates kind,
source_id and an optional validated 80-character Google-only display title.
Deleting an override removes its row. This is a new table, so DEV requires a
verified private pre-install SQLite+uploads snapshot; PROD requires the
exact 772 baseline, signed target-source review, SQLite checks, verified
private complete attachment backup and isolated restore *before* installation.
No Google network is used in any DEV tests. DEV's live Google client remains
hard-blocked.

## Test and release scope
Targeted synthetic DB, settings route, projection, existing fake Tasks sync
identity and in-place patch, completion protection, migration guard,
known regimen and DEV OAuth denial tests. No full test suite. Finish DEV
installation and user review; obtain separate explicit authorization
before starting any production stage. No credentials, logs, data or backup
archives are committed to GitHub.
