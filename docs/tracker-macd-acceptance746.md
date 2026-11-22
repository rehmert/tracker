# Release 746 MACD acceptance summary

| Domain | Verified existing operations | Remaining verification caveat |
| --- | --- | --- |
| Regimen / schedules | Add, edit, stop/archive, guarded delete, contextual day | Real-phone/owner-scoped end-to-end per mutation |
| Workout sessions / sets / equipment / routines | Add, correct, reorder, guarded delete | Full phone exercise-flow review |
| Food / Water / saved foods / templates | Add, change day/quantity, delete | Full multiuser cross-account browser traversal |
| Supplies / COAs / Labs | Add, edit, reassignment, guarded delete | Independent each-attachment lifecycle audit |
| Vials / prepared blends | Add/edit/source corrections | Whole-blend delete unsafe; preserve source custody |
| Protocols / calendar | Add, edit, reschedule, stop/hide | Historical actual dose protection |
| Notes | Add, edit/history, confirmed delete | Owner-scope and source provenance |

Move is contextual, not a universal requirement. Avoid inventing
destructive operations where history/custody requires prevention.
New Release 746 tests assert live source actions and route declarations
while older SQLite/API tests preserve recorded behavior.
