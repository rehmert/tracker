# Stage 10 — Vial form validation consistency

- Reject non-finite vial content and reconstitution volume (NaN/Infinity) in the single-vial edit form.
- Prevent marking a vial sealed if it already has logged doses, matching the bulk-edit protection.
- Clarify bulk-edit confirmation wording to avoid implying every selected record changed.
- No database migration.
- This is targeted validation hardening, not full duplicate-submission or concurrency protection.
