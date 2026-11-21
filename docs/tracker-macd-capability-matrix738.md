# Release 738 — System-wide MACD capability inventory

Status: source review against baseline Release 737 and Release 738's scoped
Regimen corrections. This table distinguishes *observed functionality*
from *remaining UI/data-policy review*. A cell marked "review" does not
assert that no backend path exists; it means system-wide availability,
visibility, owner scoping or dependency handling is not yet certified.

| Module / record type | Add | Change | Move / reassign | Delete / stop | Notes and follow-up |
| --- | --- | --- | --- | --- | --- |
| Regimen catalog items | Existing | Existing Edit medication/supplement | Reclassification by editing Kind | Medication Delete, **supplement Delete (738)**; Archive | Confirmed cascade removes dependent schedules/intakes; per-entity audit and scoped DB |
| Regimen schedules | Existing | Existing Edit schedule | Reschedule via Start/End/Time/cadence | **Delete empty (738)**; Stop with recorded history | UI suppresses delete when intake references schedule; server checks again |
| Regimen intake | Existing Log | Existing correction/Edit | Move time/day via correction | Existing Delete, visibly separate from Edit (738) | Audit preserved; responsive phone history cards (738) |
| Workout sessions | Existing Start/finish | Existing completed workout correction | Historical/backdated and session navigation | Existing accidental/completed Delete | Reverify placement and full history retention after integrations |
| Workout equipment/sets | Existing machine + set | Existing settings and set corrections | Existing routine ordering and substitutions | Existing set delete; equipment deletion requires dependency review | Preserve logged sets and machine history; never fake Delete |
| Workout routines | Existing Create/duplicate | Existing routine item management | Existing move/substitute endpoint | Existing remove routine item; routine-level Delete policy review | Confirm active sessions and historical routine relationships |
| Food entry and saved food | Existing Log/Create | Existing edit entry, edit saved food | Day/meal via correction; verify date semantics | Existing Delete food entry; saved-food deletion policy review | Hydration deletion and meal-template rename/delete already exist |
| COAs and documents | Existing create/upload | Existing edit, attachment type changes | Existing assign/unlink vials and default file | Existing Delete COA and attachment | Confirm shared-COA restrictions and default reassignment |
| Vials and preparations | Existing add/bulk | Existing vial edit, preparation edit | Inventory status/placement review | Existing guarded single/bulk vial delete and preparation delete | Preserve batch, dose and COA associations; verify owner scoping |
| Lab report/results | Existing add/import | Existing report/result edit | Date correction in report editor | Existing report/result Delete | Confirm attachment and dependent-result semantics |
| Protocols | Existing create | Existing save, cadence and date changes | Existing duplicate/activate/date editing | Existing Delete | Planned schedules vs actual dose audit must stay separate |
| Calendar projections | Derived from protocols | Underlying protocol edits | Exclusion/restore projection | Exclude/restore, not destructive delete of actual dose | Derived projections are not standalone MACD records |
| Notes and remaining pages | Existing page editing tools | Needs per-page control review | Review only where ordering or transfer is meaningful | Needs exact owner-scoped Delete/Archive inventory | Do not assume operations without a verified UI and route |
| Supplies/stock | Existing inventory workflows | Existing management | Review transfer/reconciliation policy | Review dependency-safe delete | Preserve ledger/accounting history |

## UI consistency contract

- Each actual Add/Edit/Delete/Stop/Move action must be discoverable on its
  relevant record, with consistent native links for GET and native signed
  forms for POST; no link styled as a fake submit control.
- 44px touch height minimum; keyboard focus, dark/light theme, phone-width
  overflow and confirmations must be tested in the release that modifies a
  module.
- Records referenced by actual intake, doses, purchases or COAs should
  ordinarily be stopped/archived; destructive deletion needs defined
  dependent-history policy and explicit audited confirmation.
- Never force Move just to complete a four-column matrix.

## Pending work after this integrated release

A source inventory is not a claim that every module is MACD complete.
The remaining full-scope opportunities include routine-level delete,
equipment deletion/custody policy, saved-food archive/delete, Notes owner
operations, supplies transfers, and reducing legacy CSS outside the two
proven concatenations. These should be prioritized by real user workflows,
not hidden by a blanket global CSS override.
