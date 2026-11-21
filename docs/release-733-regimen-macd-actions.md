# Release 733 — Visible Regimen MACD edit controls

Base: DEV Release 732 (1906a69408e7dd00cb9044f77cd208566aed25df), exact SHA guarded.

Medications, supplements and schedules already support native, audited
edit forms, but plain summary labels made the actions difficult to find.
This release makes explicit 44px Edit medication, Edit supplement, and
Edit schedule controls in consistent action rows near Archive/Delete
and Stop. Add shortcuts receive the same comfortable touch treatment.
Opening Edit exposes the prepopulated original form; closing it does
not submit. Schedules can be rescheduled through their existing date
and time edit fields; historical intake remains unchanged.

No backend route, database schema, permissions, deletion policy,
form names or save behavior changes. No new JavaScript.

Isolated scope: Jinja/API form persistence tests; 320/390/430/760/1024
Chromium layout and edit-open behavior; previous medication deletion,
tablet tracking and catalog regressions. No full suite.

No PROD action. Separate explicit authorization is still required.
Application-wide MACD consistency will be audited progressively.
