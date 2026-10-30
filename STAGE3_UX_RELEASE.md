# Stage 3 — Purchase and blend workflow safeguards

- Purchase pages now provide clear order → inventory → review instructions, section navigation, and anchor links.
- Blend creation requires a successful what-if preview of unchanged form inputs before enabling the Record button.
- Changing form fields invalidates the preview. A separate confirmation describes the inventory deduction before submission.
- Existing server-side validation remains authoritative; the client-side gate is a usability safeguard, not a security boundary.
- No database schema changes; no existing routes removed.
- The blend preview remains hypothetical and does not constitute validated PK or medical guidance.

Validation: template parsing, JS syntax, Python compilation, ZIP integrity. Not exercised against live database.
