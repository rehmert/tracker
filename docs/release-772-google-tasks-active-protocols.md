# Release 772 — active protocols only in Google Tasks settings

Baseline: DEV and PROD Release 771, commit
`ac330a08ffa4ff49ca86e034b9aa81f4e583a8c7`.

The existing Google Tasks projector already excludes inactive and hypothetical
protocols. This release aligns the settings UI with that behavior: only
`Protocol.is_active = true` items appear in the protocol publishing controls.

Inactive/what-if protocols remain in Tracker, retain their exclusions, and
cannot generate future Google Tasks. Activating a protocol makes it appear in
the controls; deactivating it hides it and the existing sync will remove
future incomplete tasks. Completed historical tasks are retained in the
separate inventory-reconciliation section for audit.

Medication and supplement settings remain unchanged. No schema, migration,
OAuth, service, dependency or Google API changes. DEV never connects to Google.
Qualification and DEV install only without separate explicit PROD approval.
