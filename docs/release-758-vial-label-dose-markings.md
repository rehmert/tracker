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


The post-mix dose-marked 40x20 label compacts recorded physical volume
and the exact concentration basis used for the U-100 calculation into
one printable line. The label fit validator requires the complete
target, volume/concentration, mixing/BUD/expiration dates (if provided),
and vial identifier rather than silently truncating a safety field.


## User-selected four-line post-mix label format

The user-facing reconstituted label is now exactly:

1. Compound / purchase vendor
2. Labeled vial content / explicitly selected COA reported content
3. Recon date / BAC-water volume / final effective mg/mL
4. Target mg = approximate U-100 syringe units

COA reported content is a *per-vial amount*, not mg/mL before
reconstitution. The chosen report is shown for comparison; final
mg/mL and U-100 marks still use Tracker's canonical dose-log
effective content (label value, or the COA-average if opted in).
An explicit single-vial COA picker uses only linked reports.
Multiple reports without a designated primary are not selected
arbitrarily. Missing fields are printed N/A. The recorded
reconstitution liquid volume is used as the BAC-water amount for
lyophilized vials; no BAC-water supplier or diluent identity is
inferred. IU-based vials retain IU/mL and never pretend IU means mg.

The 40x20 normal label uses a compact horizontal glyph variant for
all four lines in PNG without changing 203-DPI geometry or legacy
unreconstituted labels. All other rotations/layouts are rejected
for post-mix four-line output to prevent clipped fields until they
support the same typography. Long names/vendors are not truncated:
the UI shows a print-fit warning, and downloads fail closed.
No inventory, schedule, dose or COA data is modified.

The user-selected four-line format does not include the historical
separate expiry/BUD lines. The label previews explicitly warn that the
mixing date is not an expiration or beyond-use date; those recorded dates
remain in the vial details and are never calculated or altered.
