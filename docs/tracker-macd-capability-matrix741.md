# Tracker MACD — integrated Release 741 inventory

| Module | New or visible MACD operations | Existing operations kept | Historical protection |
| --- | --- | --- | --- |
| Supplies | Edit name/notes, reassignment for unused matching-unit category, guarded Delete | Add, use, pill use, inventory count reconciliation, purchase pricing | Usage and stock adjustments bar Delete; preserve purchase row, private edit/delete audit |
| Supply categories | Rename and change unit only while unstocked, Delete unused custom category | Add category | Built-in keys fixed; category with stock cannot Delete or switch unit |
| Vials | Direct Edit shortcut and record-level Manage | Existing lifecycle Edit, bulk reassignment, guarded Delete, preparations | Original dose/COA/consumption rules unchanged |
| COAs | Visible Edit, Documents, Vial links, Delete destinations | Attachment uploads, identifiers, verification, reassignment, Delete | Existing shared-COA checks unchanged |
| Prepared blends | Manage recorded individual draws and source composition | Dose/waste, correction/Delete withdrawal | No whole-blend Delete: source transfer custody remains immutable |
| Labs | Direct report Edit, analyte management, Delete destinations | Result and report mutations | Existing report/file provenance protections |
| Protocols | List Edit, Duplicate, Stop/Activate, Delete | Full editor, dates/cadence | Actual administration logs are independent |
| Calendar | Direct Edit source schedule, Hide/Restore | Date review, log dose | Only projected protocol schedule is changed |
| Notes | List Edit, History, confirmed Delete; delete metadata audit | New note, source add/delete, revisions | Delete audit excludes note body |
| Mobile UI | Common action buttons, chevrons, keyboard focus and phone touch targets | Existing theme/density + legacy CSS order | Behavior and navigation retained |

Notes: contextual Move has meaning for scheduling, reassignment and ordering,
not every record type; forbidden destructive operations must be visibly
disabled or omitted and rejected by the server. Full app-wide CSS retirement
is not claimed.
