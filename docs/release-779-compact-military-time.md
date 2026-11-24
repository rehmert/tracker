# Release 779 — colon-free 24-hour time entry across Tracker

**Goal:** Allow users to type military time as **HHMM** or **HMM** without
a colon. Examples: \`0730\` → \`07:30\`, \`930\` → \`09:30\`,
\`2130\` → \`21:30\`, \`0000\` → \`00:00\`, \`2359\` → \`23:59\`.
Existing \`HH:MM\` input continues to work. Invalid values such as \`2400\`,
\`2360\`, \`999\`, \`25:00\` are rejected.

Tracker already has a universal 24-hour text proxy for native HTML
\`time\` and \`datetime-local\` fields, including dynamically inserted
HTMX/workout controls. Extend its parser and visible validation to accept
the compact form while the **original named native input** always carries
canonical \`HH:MM\` or \`YYYY-MM-DDTHH:MM\` to existing server handlers.

- Normalize the visible entry at blur/change/submit without adding another
  field or removing the current 24-hour UI.
- Preserve the original named input, CSRF/HTMX behavior, existing display
  synchronization, required/disabled controls and native fallback.
- Update the older dose/vitals adapter for standalone consistency.
- Bump the universal and legacy script asset URLs for browser cache refresh.
- No database changes, timezone changes, existing timestamps alterations,
  new dependencies, or updates to any dosing/schedule interpretation.

Tests execute both adapters in Node with a minimal browser-like DOM,
checking ordinary times, shorthand, invalid values, datetime composition,
programmatic updates, form submit, and dynamically added time controls.
Also run the existing 371/713, regimen and UI coverage in scoped QA.

DEV only until separate explicit PROD authorization.
