# Release 758 — Planned mg and vial-specific U-100 units on mixed-vial labels

Base: DEV-qualified Release 757, commit
90b297fc07c950d5a44a0bf8fe7d4beabfd8b30f. PROD remains on
Release 755 until explicit promotion. This is one focused follow-up release
because DEV qualification receipts are immutable.

## Behavior

- Reconstituted/post-mix labels may include a compact "TARGET:<mg>MG
  U100:<marks>" line. "U100" means U-100 syringe volume markings,
  NOT International Units (IU).
- An existing current active protocol's mg, mcg or g amount may be
  suggested only when exactly one distinct target exists for the compound
  in currently active schedule stages. Inactive, future, ended, ambiguous,
  or volume-based protocols are never converted to an invented target.
- The single-vial post-mix label page supports an explicit target mg in
  its GET-based preview controls; it does not edit the saved protocol.
  Preview and PNG/SVG links carry exactly the same selected target.
- Concentration is derived from the same canonical per-vial inventory
  data used in Dose Log and Calendar, including an explicitly enabled
  effective-content/COA override, if applicable. On these labels the
  printed mg/mL concentration matches the concentration used to calculate
  U-100 markings. Each vial is calculated independently.
- Missing usable recorded liquid volume/concentration or insufficient
  recorded remaining mass prevents a fabricated syringe value. A
  user-selected target without a safe conversion cannot be exported.
- Sheet/bulk labels include target and syringe markings for each
  reconstituted vial with one unambiguous current mg target and adequate
  concentration/stock; every vial is independent.
- The 203 DPI label renderers have finite glyph rows and characters:
  reject a printable target label if the full target/U100 line would be
  truncated for its selected layout/rotation. 40×20 mm with normal text
  direction is recommended. The legacy 10×20 strip generally cannot fit
  such a line legibly. Small-layout failures tell the operator to select
  a larger layout. Never silently drop or cut the numeric dose/markings.
- Original content, mixing date, BUD and vial identity remain on a
  properly sized label. Optional lot/cap/expiry fields may be omitted by
  the legacy row-limited renderer; BUD is prioritized.
- Neither label generation nor calculated target previews create DoseLogs,
  mutate inventory, edit protocols, prescribe a treatment, or select a vial
  for administration. The physical vial and syringe graduations must
  still be verified before an actual administration.

## Qualification

Run only synthetic isolated label, conversion, batch layout, server preview,
PNG/SVG, related historic label regression and route tests. Use the existing
guarded scripts/tracker-release.sh DEV-first. No database migration or full
suite. Require explicit user authorization before DEV-controlled PROD
promotion. Do not put actual clinical data into GitHub code or QA receipts.
