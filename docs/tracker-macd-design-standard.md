# Tracker MACD (Move, Add, Change, Delete) interaction standard

## General principle
Records the user manages should offer discoverable Move, Add, Change,
Delete actions **where those operations make domain sense**. A visible
control must carry out its advertised operation. Do not force artificial
Move operations onto records that cannot meaningfully be moved.

## Design contract
| Operation | Behavior |
| --- | --- |
| Move | Reschedule, reorder, recategorize or reassign when safe, maintaining historical references. |
| Add | Obvious collection-level Add/Create entry point; native labeled form. |
| Change | Clearly labeled Edit [type] on cards and rows; existing values prefilled; Save explicit. |
| Delete | Confirm consequences, check dependencies and ownership; retain audit trail; offer Archive/Stop to preserve historical records. |

- 44px minimum touch controls and consistent button styling.
- Never bury Edit inside ambiguous or unlabeled disclosures.
- Preserve CSRF protection, multiuser scoping and audit history.
- Distinguish Archive/Stop from permanent Delete.
- Use module-scoped database and Chromium tests for every change.
- Avoid blanket application CSS rewrites or introducing fake actions.

## Progressive system-wide review
Start with Regimen in Release 733, then inventory the actual actions
for Workout, Food, Vials/Blends, COAs, Labs, Calendar, Supplies,
Protocols and Notes. Verify Move/Add/Change/Delete independently for
each record type before considering the domain complete. Do not claim
application-wide coverage until audited.
