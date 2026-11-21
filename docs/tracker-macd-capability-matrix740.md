# Tracker MACD capability matrix — through Release 740

This is an incremental amendment to docs/tracker-macd-capability-matrix739.md.
A source audit is not certification that all app modules are complete.

| Entity | Add | Move | Change | Delete / Archive | Data/history policy |
| --- | --- | --- | --- | --- | --- |
| Regimen medications/supplements | Create | Reclassify | Edit | Delete/Archive | 738 audited dependents |
| Regimen schedule/intake | Schedule/log | Time correction | Edit | Stop or guarded Delete | Actual intake history retained |
| Workout routines | Create/Duplicate | Ordered exercise Move | Edit name (739) | Delete unused (739) | Session references block Delete |
| Workout equipment | Add | Routine exercise order only | **Edit name/gym/manufacturer/model (740)**; Machine Setup unchanged | **Delete unreferenced (740)** | Logged sets, routine memberships and frozen session targets block deletion; audit before/after; retired QR preserved |
| Workout sets/sessions | Log | Correct historical date | Edit | Existing Delete | Record-level workout semantics |
| Saved Food | Create | Reuse in meals | Edit | Delete unreferenced (739) | Actual meals and templates block Delete |
| COA/vials/labs/protocols | Existing Add | Context-specific | Existing Edit | Guarded Delete/Stop | Further review by dependency |
| Supplies/Notes | Existing | Context-dependent | Needs further review | Dependency policy still under audit | No ledger or history erasure |
| Calendar | Derived | Reschedule source | Edit source | Exclude/restore projection | No deletion of actual logged doses |

UI contract: visible real actions with 44px touch targets, native GET or
form POST controls, focus visibility, dark/light legibility, irreversible
confirmation, version protection where necessary and owner-scoped writes.
