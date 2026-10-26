# Tracker Release 3

Built on the working Release 2 dark-mode package. No external health integrations.

## New pages and functionality
- `/calendar`: read-only monthly calendar of actual logged doses and projections from active protocols. Select a month and **explicit anchor date**. Projections are not clinical schedules, do not log administrations, and do not affect inventory. Approximate fractional-day and monthly frequencies are labeled as such.
- `/pk`: compare up to four saved hypothetical scenarios for the selected compound, including a recorded-dose/no-future-dose baseline. Existing simulator and saved scenarios are preserved.
- `/labs/compare`: side-by-side report comparison, canonical analyte matching, and arithmetic differences when units match or a supported conversion exists. Unknown conversions show a dash.

## Deployment
Back up SQLite and uploaded files, deploy application code, preserve `.env` and `data/`, restart the service, then hard-refresh Chrome (Ctrl+Shift+R). No schema changes are required.

## Limitations
Calendar is a projected repeating schedule, not a reconciliation engine: it does not mark projected events as missed, or match actual doses to projected events. Anchor date is user-entered. PK curves are not serum concentrations or dosing guidance. Lab comparisons are descriptive only.
