# Protocol escalation stages

- Each protocol item has a Start week (1-based) and optional End week (inclusive).
- Add the same compound in successive non-overlapping stages to model changing amounts or frequency.
- A blank end week continues until the protocol end date, if set.
- Stage overlap for the same compound is rejected; separate compounds may overlap.
- Horizon estimates account for the number of weeks each stage is active. The per-week and per-month numbers shown for each row describe its active stage, not an average across the entire horizon.
- Calendar projections show only dates inside the item's stage; dashboard current weekly inventory use counts only the currently active stage.
- Migration adds two columns to protocol_items with defaults, preserving existing entries and all other data.
- This is a recordkeeping/what-if tool, not an escalation recommendation or an automatic dosing scheduler.

## Deploy

Back up your live database and installation before deploying. Extract the full release to your working tree while retaining `.env`, `data/`, `backups/`, and other live user files. Restart `tracker.service`; the migration runs at startup. Hard-refresh the browser.
