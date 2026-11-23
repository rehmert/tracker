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
Different recorded concentrations: display physical volume and flag
"Mixed concentrations - review", with no asserted weeks coverage.
Only equal-strength eligible vials get a coverage estimate.

Expired, beyond-use, closed, finished and discarded vials remain excluded.
No database changes or dosing guidance.

The dependent horizon, scheduled-demand and shared-stock audit pages now
accept unknown stock, and their CSV outputs leave unknown cells empty.
Interval frequency: one administration every N days, weekly dose = 7/N.

Qualification is restricted to synthetic in-memory ORM and relevant
forecast regression tests. Requires DEV qualification and separate PROD
promotion authorization.
