# Release 712 — U-100 syringe units as recorded withdrawal volume

**Base:** Release 711, `7c662491c3a233b3df60842bbaeaa2dfbc995f06`

## Behavior

Users may enter **units (U-100 syringe)** in the shared `/doses`
ordinary-vial and prepared-blend forms and in both correction forms.
**1 unit = 0.01 mL**, so 20 U-100 syringe markings = 0.20 mL liquid.
This is a syringe's volumetric scale, **not IU (International Units)**.

The unit parser canonically stores the input as `entered_unit="units"`
and `entered_value` as entered; inventory still deducts the original
physical amount: `DoseLog.amount_base` for ordinary vials, and
`BlendDose.volume_ml` for prepared blends. No source-vial transfer or
constituent dose is created during a blend draw.

For a known-concentration ordinary vial, volume is converted to native
mass or IU by concentration. For a mixed-compound prepared blend,
recorded liquid volume determines all constituent doses. The normal
dose preview shows the calculated compound content and liquid volume,
and both correction pages can retain the U-100 syringe unit as entered.

Syringe-unit entries are rejected if the ordinary vial has no known
liquid volume, if the volume would exceed inventory, or if any other
existing dose validation gate fails. Existing `IU` remains a separate
potency dimension. **Protocol dose selection and vial content units
remain unchanged**, avoiding an ambiguous volume/potency schedule.

Only the U-100 syringe scale is supported by `units` in this release;
other syringe types (such as U-40) must use explicit mL/uL, not `units`.

## Qualification

Change-scoped qualification, isolated from DEV/PROD data, runs in a
`PrivateNetwork=yes` systemd unit with a temporary detached Git
worktree and a separate disposable SQLite database.

- `tests/test_release712_u100_withdraw_units.py`: real signed API
  preview, create, edit and repeat; mixed blend inventory; IU separation;
  rejects missing volume/overdraw; protocol selectors remain unchanged
- Existing unit conversion, vial/blend corrections, audit and inventory
  tests remain in the scoped backend gate
- `tests/browser/test_u100_withdraw712.py`: real strict-CSRF Chromium
  HTTP and HTTPS through the single standard dose form, including
  source-switch resets and preventing constituent double charges
- Versioned browser qualifier registers targeted strict
  `u100-withdraw712`, and keeps the fixture in full strict mode
- PROD guarded release runner repeats the scoped qualification

No schema changes or automatic migration. The DEV rollout is
`scripts/tracker-qualify712.sh` then exact-SHA signed guarded
`scripts/tracker-install712.sh`; PROD requires separate explicit user
authorization and signed DEV-controlled promotion.
