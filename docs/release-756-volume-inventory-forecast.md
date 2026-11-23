# Release 756 - Volume and interval inventory forecasts

The active Test C protocol is expressed in mL and scheduled once every
three days. The former forecast excluded every mass-based vial and could
not calculate interval demand. This read-only change supports both.

Source quantities come from canonical vial_views, honoring COA opt-in,
logged dose/waste quantities, and transfers into blends. A volume plan
requires recorded vial volume and concentration: physical remaining liquid
is remaining_base divided by conc_per_ml. Concentration is never guessed.

Concentrations absent for all matching vials: remaining stock is unknown
(dash), not falsely zero; show "Concentration unavailable". If only some
vials lack concentration, show known physical volume but no weeks estimate.
Different recorded concentrations: display physical remaining volume and
volume-based weeks of supply, flagged "Mixed concentrations - review".
Different strengths are never treated as equivalent milligram dosing capacity.

Expired, beyond-use, closed, finished and discarded vials remain excluded.
No database changes or dosing guidance.

The dependent horizon, scheduled-demand and shared-stock audit pages now
accept unknown stock, and their CSV outputs leave unknown cells empty.
Interval frequency: one administration every N days, weekly dose = 7/N.

Qualification is restricted to synthetic in-memory ORM and relevant
forecast regression tests. Requires DEV qualification and separate PROD
promotion authorization.

The dashboard's "Inventory forecast" panel and protocol summary also now
derive liquid quantities from per-vial concentrations. Missing concentration
flags unknown stock; mixed strengths show physical volume with a warning
rather than claiming equivalent milligram dosing capacity.
Existing mass/IU dashboard semantics are unchanged.


## Release 756 Calendar extension (same release branch)

A recorded target in mass (mg/mcg/g) is the authoritative planned
quantity. Calendar review list and day cells now expose an explicit vial
picker with read-only conversions based on the selected eligible vial's
**recorded effective** content (including opted-in COA) and liquid volume.
The calculation shows target mg, vial strength in mg/mL, withdrawal in mL,
and U-100 syringe markings. Vials with missing concentration, insufficient
recorded mass, incompatible units, invalid dates/status, or no stock are
not selectable and generate a clear notice. No concentration is borrowed
from a different vial. Select is blank until a user explicitly chooses.

The selected vial and original mass-based plan are carried via GET to
the existing Dose Log. Dose Log performs its existing server-side
independent amount/concentration validation and saves nothing until the
user submits the recording. Calendar and preview perform no writes.

For legacy volume protocols, mixed recorded strengths still trigger a
warning, but valid physical remaining volume can yield a volume-only
weeks estimate. Different mg/mL strengths must not be treated as
equivalent amounts of delivered drug. U-100 markings are NOT IU potency.
