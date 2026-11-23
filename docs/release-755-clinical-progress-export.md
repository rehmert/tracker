# Release 755 — Complete clinical progress history (explicit opt-in)

Base: Release 754 at acc89f3ebfc0e8f6a8fd37b1f2e1cf1e92762dcd.

## Source selection

Config under root-owned /etc/tracker-progress-export.json gains **optional**
boolean flags (default all false): export_all_labs, export_all_regimens,
export_all_compounds. Existing configs without these keys still work and
continue to OMIT these protected categories by default.

- export_all_labs: all numerical lab_results with dates, analytes, units,
  and reference ranges; never lab name, notes, reports, attachments or IDs.
- export_all_regimens: medication and supplement schedules, with strength,
  ingredient, form, cadence, planned amount, start/end dates, active status,
  including 731 tablet dose values where available; separately logged
  taken/skipped entries and recorded tablet administration.
- export_all_compounds: logged vial doses and blend administrations plus
  currently active protocol items. What-if protocol items are labeled plans,
  never presented as actual administration. Waste/disposal logs excluded.

Data remains *read-only* and derives from one SQLite snapshot using explicit
column SELECTs; no live ORM objects, writes or schema migrations. Dates are
limited to the configured 365-day window by default, except active plans
which describe the present regimen. Only fields necessary to analyze
progress are emitted. Avoid *any* names of vendors, vials, prescribers,
document filenames, patient identifiers, raw notes, source images or COAs.

Schema version v2 introduces additional lab selection information and
structured intervention events. Existing v1 schema remains in application
source for prior exports. On promotion the repository's manifest and v2
schema are replaced atomically; Git history can retain older versions.

## DEV acceptance and production operations

Run focused synthetic tests for all categories, opt-in and default-off
behavior, medication vs supplement handling, planned vs actual event
separation, peptide/injectable dose and blend output, forbidden field
exclusion, and zero source modifications.

DO NOT reconfigure PROD or enable the new flags during DEV qualification.
Only after the user separately authorizes PROD may operators promote the
pinned commit and then safely update the root-only PROD configuration to
set all three opt-ins true, preserving existing token_file, repository,
duration and prior permissions. The nightly systemd timer can remain active;
manual first real export and independent private GitHub read-back should
validate the newly enabled scope.

Never copy real clinical data into the application's GitHub repository or
release receipts/logs.
