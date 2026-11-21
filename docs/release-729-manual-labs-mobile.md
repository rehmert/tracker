# Release 729 — Responsive manual Labs entry

**Installed base:** Release 727 `3718936aedfcb1b8fe243c86fe6fc7e06a7a41d2`.

Saved Labs reports became mobile cards in 727. Manual analyte entry still used
a six-column horizontally scrollable table. Release 729 applies the same
established card-table style to the original manual table and row partial.

The five original inputs receive phone-only visual labels, the analyte name
spans the full card, and the original Remove action remains in the same row
with a 44px touch target. All inputs get 44px height and 16px font on phones.
Entry-method links, incomplete-field review and saved-layout submit controls
also receive minimum 44px tap targets.

No new JS or backend changes. The two POST forms, their signed input contract,
dynamic HTMX Add Row, inline Remove, duplicate detection, review and
validation, attachments, and desktop table semantics remain unchanged.

**QA:** pinned exact target + changed-path allowlist; private detached
PrivateNetwork worktree; Jinja and source regressions; existing signed form,
CSV, duplicate, review and Release 704 sticky-action tests; 320/390/430/760/
1024 Chromium across dark/light and all densities, FormData preservation and
dynamic-row layout. Full application suite not requested.

Allow automatic isolated qualification then verified DEV installation.
PROD requires separate explicit approval. This is the UX increment
before measured performance, dependency reproducibility, and strict CSRF.
