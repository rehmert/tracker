# Release 758 — Production-date vial labels (two lines / four lines)

Built on DEV-qualified Release 757 (commit
90b297fc07c950d5a44a0bf8fe7d4beabfd8b30f).
Release 758 remains DEV-first; PROD stays on Release 755 until explicitly
authorized. Release 758's GitHub source branch is still unqualified as of
this code change. No existing receipt is replaced.

## Requested print formats

Lyophilized / unreconstituted (exactly 2 lines):
    COMPOUND / VENDOR / PRODUCTION DATE (MM/DD/YY)
    LABELED VIAL CONTENT / SELECTED LINKED COA CONTENT

Reconstituted (exactly 4 lines):
    COMPOUND / VENDOR / PRODUCTION DATE (MM/DD/YY)
    LABELED VIAL CONTENT / SELECTED LINKED COA CONTENT
    RECON DATE (MM/DD/YY) / RECORDED BAC WATER / EFFECTIVE mg/mL
    TARGET mg = CALCULATED U-100 SYRINGE MARKS

Example using fictitious product/source data:
    TEST PEPTIDE / TEST VENDOR / 11/01/26
    10mg / 11.2mg
    11/22/26 / 2mL BAC / 5mg/mL
    1.4mg = 28 units

The second line is *content per vial*, not solution concentration;
a COA-tested amount never silently replaces nominal content. Final mg/mL
and syringe markings use the same canonical effective content settings
as Calendar/Dose Log (label unless the existing COA-use option is enabled).
The individual label page allows selecting a linked COA for display.
If ambiguous, no COA is automatically chosen. Every printed number is
vial-specific; IU potency is never equated with U-100 syringe markings.

## Real manufacture date — nullable additive migration

Tracker has no manufacturing/production date before this release; it MUST NOT
use Purchase.purchased_on, Coa.tested_on, received_on, created_at, or expiry
as a substitute. Release 758 adds nullable Vial.production_on and an
idempotent SQLite migration ("ALTER TABLE vials ADD COLUMN production_on
DATE"). No existing records are backfilled or rewritten.

Users can enter or correct a production date from Purchases > Add Vials,
Vial Details > Edit, or the Vials bulk editor. The stored value is a true
date; it prints MM/DD/YY; unknown dates print "N/A" in both label types.
Unreconstituted labels do not invent a mixing date or dilution value.

## Print-format and safety details

The default for all vial-label routes is one physical 40×20 mm sticker (203
DPI). This avoids consuming a paired 30×15×2 strip when only one label is
needed. The single-vial preview/export and selected-vials sheet/exports all
default to 40×20, with exactly one label per physical strip. 30×15 single,
30×15×2 paired and 50×30 single remain selectable alternatives.
The exact two-/four-line formats share horizontally condensed 5×7 bitmap
glyph geometry in PNG and SVG, two vertical pixels per dot, corresponding
roughly to a 6.5-point-class label font. The 40×20 output uses its extra
vertical space for row separation; 30×15 rendering remains unchanged.
Neither export silently truncates complete values. Overlong compound/vendor
names trigger a fit warning. Normal (0°) orientation is qualified for
compact text; legacy labels retain their existing renderer.

Unlike the previous implementation, the fit check uses the actual
30×15 pixel geometry used by both exported formats. Bulk sheet PNG and
SVG compose distinct complete stickers without re-scaling or
changing existing strip dimensions.

The four-line output intentionally has no separate expiry/BUD row.
Those recorded dates remain visible on the vial detail page and are
not recalculated. Do not confuse manufacturing date or mixing date
with sterility, safe use, or beyond-use expiry.

Reconstitution liquid volume comes from the recorded vial preparation.
Tracker records the volume used for lyophilized reconstitution; the
label indicates BAC-water volume as recorded in Tracker, not a verified
diluent brand/sterility assay. Missing values remain N/A.

Label preview and download are GET/read-only. No printed operation
changes vials, COA links, dose logs, protocols, or inventory.

## Qualification

Run targeted regression:
- synthetic 2-/4-line exact content and native 203-DPI PNG/SVG
- COA selection, effective concentration and U-100 units
- database schema migration idempotence and nullable production dates
- purchase add, individual edit and bulk-date form entry
- historic printable labels, media/rotation and UI handoff regression

No full suite unless a shared-core dependency or migration boundary
requires expansion. Protect the DEV/PROD database backups, never write
medical data or raw logs into GitHub. Await explicit owner PROD authorization.

Both label formats intentionally omit the separate expiry/BUD rows.
The UI explicitly explains that manufacturing and reconstitution dates
must not be mistaken for expiration or beyond-use determinations.
