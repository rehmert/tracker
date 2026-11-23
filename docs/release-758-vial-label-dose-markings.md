# Release 758 — exact four-line post-reconstitution vial labels

Source base: DEV-qualified Release 757
(90b297fc07c950d5a44a0bf8fe7d4beabfd8b30f).
Release 758 remains DEV-first and requires a fresh immutable
qualification receipt. Production remains at Release 755 until an
explicit, separately authorized promotion.

## User-requested output

For every reconstituted (post-mix) single-vial or bulk-sheet label,
print exactly four lines in this order:

    COMPOUND / VENDOR
    LABELED CONTENT / SELECTED COA TESTED CONTENT
    RECON DATE / BAC WATER AMOUNT / FINAL mg/mL
    TARGET mg = CALCULATED U-100 SYRINGE UNITS

Example, entirely synthetic:

    TESAMORELIN / BLACKFIN SUPPLY
    10mg / 11.2mg
    11/23/26 / 2mL BAC / 5mg/mL
    1.4mg = 28 units

Missing/unknown values display N/A, not guessed numbers. Content
in line 2 is amount per original vial (e.g. mg); the third line is
the final solution concentration (mg/mL). IU-based vials retain IU/mL,
never an invented mg value, and do not get an mg dose conversion.

## Sourcing and effective content

- Compound from linked compound record; vendor from purchase.vendor.
- Labeled content from Vial.content_value/content_unit.
- Tested content from an explicitly selected COA linked to this vial.
  The individual label form has a COA selector. Its primary linked COA
  is the default; a sole linked COA is selected; multiple linked COAs
  without primary are ambiguous and display N/A until the user chooses.
  A selected COA changes only the displayed comparison value.
- Reconstitution date from Vial.reconstituted_on. For lyophilized vials
  BAC-water amount uses the recorded Vial.volume_ml (which Tracker's
  reconstitution form labels "BAC water added"). No source brand,
  sterility status, or other diluent chemistry is inferred. Liquid
  non-lyophilized vials use VOL rather than a BAC claim.
- Final concentration is canonical vial_views.concentration: nominal
  label content by default, or the existing COA-average if the user
  has opted into that inventory setting. The selected COA comparison
  does NOT independently replace the canonical dose calculation.
- Target mg from exactly one current active, mass-based protocol target,
  or an explicit individual-label override. Multiple conflicting
  active doses are not picked arbitrarily. Actual U-100 syringe marks
  are (target mg / vial-specific mg/mL) × 100, not IU potency.
- Only recorded eligible mass/concentration supports numeric syringe
  markings; missing data prints N/A without inventing a dose.

## Print and security contract

The four lines require 40×20 mm and 0° orientation in this release.
The four-line PNG renders condensed horizontally (still 203 DPI)
and existing label generations keep their original renderer.
All four lines must fully fit SVG and PNG output; long vendor/compound
strings fail closed with an actionable layout warning.
Other rotations/strip widths are rejected for post-mix four-line
labels until equivalent print-fit guarantees exist.

Reconstitution dates are not beyond-use or expiration dates.
The requested strict four-line format omits dedicated BUD and expiry
rows. UI preview/download and batch-sheet screen explicitly warn
users to consult the saved vial record for expiry/BUD.

Unreconstituted labels remain unchanged. Both label sources and
GET preview/export functions are strictly read-only. No schedules,
dose logs, inventories, linked COAs or purchase records are changed.
Only synthetic fixtures and focused test modules run in qualification.
