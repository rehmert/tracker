# Tracker MACD capability matrix — through Release 739

This is an incremental source-verified update to docs/tracker-macd-capability-matrix738.md, not a declaration that every app record now supports all four operations.

| Record | Add | Move | Change | Delete / Archive | History/data contract |
| --- | --- | --- | --- | --- | --- |
| Regimen items | Create | Kind change | Edit medication/supplement | Delete both, Archive | Release 738 audited dependent cleanup |
| Regimen schedules | Create | Date/time update | Edit | Delete only empty; Stop otherwise | Actual intake prevents schedule delete |
| Regimen intake | Log | Date/time correction | Edit intake | Delete intake | Private audit |
| Workout routines | Create/Duplicate | Reorder/substitute exercises | Edit routine name (739) | Delete unused (739) | Historic/active workout sessions prevent delete; audited edits and deletes |
| Workout plan rows | Add exercise/goal/schedule/group | Move exercises up/down | Modify plans | Remove exercise or delete unused routine | Planning only; preserve actual sets |
| Workout sessions/sets | Start/log | Backdate/correct | Edit | Existing Delete | Retain historical workouts unless explicitly deleted |
| Saved foods | Add via journal | Use in meal/template | Edit | Delete unreferenced (739); favorite toggle | Historical meals or templates block Delete; stale-version guard |
| Food entries/templates | Add | Day/meal edit | Edit/rename | Existing entry/template Delete | Journal consistency |
| COA/vials/labs/protocols | Existing Add | Contextual assignment | Existing Edit | Guarded Delete/Stop where appropriate | More per-record dependency auditing to do |
| Notes/supplies/equipment | Existing flows | Context-dependent | Further review | Dependency-safe delete policy unfinished | Do not erase linked history or invent Move |
| Calendar | Derived | Reschedule source | Edit source | Exclude/Restore projection | Actual logs unchanged |

## Common contract
Make real actions discoverable beside each record. Use 44px+ controls,
keyboard focus and native form submissions. Explain irreversible Delete
dependencies, offer Stop/Archive when deletion would destroy recorded
history, and retain per-user scoping and existing write protections.
