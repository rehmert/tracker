# Tracker v2.3 — COA history, verification and decimal displays

- COA review status: unreviewed / verified / rejected / needs review, with notes and timestamp.
- Immutable before-change metadata snapshots on edits and review changes; stored in `coa_revisions`.
- Compare COAs by linked vial compound+lot or matching job/task ID. Multiple certificates remain separate records.
- Inventory Intelligence, lab comparisons and lab chart labels use ordinary decimal notation instead of scientific notation.
- Additive database migration: `coas` verification columns and new `coa_revisions` table. Back up before upgrade.
- Replaced COA files are not retained, only their prior filename/hash metadata in revision history.
- Review status is user-recorded, not proof of authenticity.
