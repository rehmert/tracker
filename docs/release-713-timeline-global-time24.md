# Release 713 — Concise blend timeline and 24-hour time entry throughout Tracker

**Exact DEV baseline:** Release 712 `1f2982975494ece2bceea3ce85617447f712b399`

## Administration Timeline

The `/doses` Administration Timeline displays the **recorded amount and unit only**
for each prepared-blend withdrawal, e.g. `10 units`, without adding
`· 0.1 mL withdrawn` or an injection-site suffix in the Amount column.
This does not recalculate or reinterpret historical entries; a draw originally
entered in mL or IU continues to display that entry's own unit. The recorded
`BlendDose.volume_ml` and its concentration-based constituent calculations,
correction history and remaining inventory are unchanged. Detailed blend
history retains a dedicated withdrawn-volume column.

## All time-entry controls

Add `tracker-time24-global713.js` and its mobile-aware CSS to
`app/templates/base.html`, covering both `<input type="datetime-local">`
and `<input type="time">` across dose, vitals, regimen, PK, workout,
preparation correction and dynamically inserted forms.

Browsers may display native time controls with AM/PM according to browser
locale, even when the underlying value is `HH:MM`. The enhancer replaces
**visible** time entry with explicitly validated text `HH:MM` on a
24-hour clock (00:00–23:59), with an accompanying date control for full
timestamps. The original native field remains *named* and hidden, receives
the canonical ISO local-wall-clock string and fires input/change events so
existing client and server data contracts remain intact. The 371 adapter
still exists and is protected against double-enhancement. Proxy fields have
no `name` attribute and never duplicate submitted data.

Focus synchronization covers PK scripts that assign native input values
directly. Form resets and newly injected DOM controls are covered. No
timezone conversion, AM/PM notation, timestamp migration, dosing, or
inventory change is performed.

## Qualification and deployment controls

DEV qualification is exact-commit pinned, `PrivateNetwork=yes`, uses a
disposable worktree and isolated SQLite database, and does **not** install
the candidate. Scope includes:

- A real test database rendering a prepared-blend withdrawal as only
  `10 units` in the timeline, while confirming no inventory mutation.
- Source contracts verifying all native time entry templates load the
  global 24-hour script, and retain the existing required field names.
- Backend unit, blend, regimen, workout, PK and 371 time-adapter regressions.
- Strict-CSRF Chromium HTTP and HTTPS coverage for dose, vitals, regimen,
  workout backfill, PK, mobile today, programmatic value synchronization,
  invalid times, and dynamically inserted time fields.
- Scoped JS syntax and deployment-runner checks. Full suite not requested.

After qualified, a separate guarded `scripts/tracker-install713.sh`
may install the exact commit on DEV. PROD requires separate, explicit
user approval, signed DEV-controlled promotion, and its own scoped test gate.

No schema or data migration.
