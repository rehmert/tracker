# Tracker time-entry UX contract

For all future forms requiring a clock time, prefer 24-hour entry with
**both** \`HHMM\` (or \`HMM\` for single-digit hours) and \`HH:MM\` accepted.

- Display and submit normalized \`HH:MM\` in local wall-clock time.
- Reject hours after 23, minutes after 59, and all AM/PM ambiguity.
- Never change the meaning or timezone of an existing saved timestamp.
- Support keyboard, mobile, accessibility, and dynamically inserted fields.
- Keep original named time inputs and established server-side validation.
- Test both valid/invalid shorthand and validation with normal and HTMX
  forms; do not force a new standalone page for simple time editing.
