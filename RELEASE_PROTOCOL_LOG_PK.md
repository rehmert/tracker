# Protocol dose logging and PK protocol selection

- Dashboard and calendar planned doses have a **Log dose** link. It opens the existing dose entry form with compound, scheduled date/time, amount and unit prefilled. The user must select/confirm a vial and explicitly submit; no dose is logged by following a link.
- PK Simulator now has a **Protocol** dropdown. Select an active, dated protocol, then the compound, to model the protocol's future scheduled doses. Escalation stages, weekdays and dosing time are honored. The simulation is read-only and does not alter scenarios, dose logs or inventory.
- Only mass-based doses can be represented in the PK model (mg, mcg, g); IU is excluded.
- No database migration required.
- Back up data and app before installing. Restart tracker.service and hard-refresh browser.
