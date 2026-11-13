# Release 596 — Vendor-pricing multipart and CSV CSRF witnesses

Base: Release 595 \`fd0e3b2817c282d4da1ffe99f13aacdad416b9c7\`.

Seven previously unqualified vendor-pricing unsafe routes now have source-mapped,
full-gate browser test candidates:

- Attachment multipart upload and signed deletion, plus byte-for-byte
  authenticated download verification (no import side effect).
- Structured CSV multipart preview and reviewed CSV save, with no writes
  during preview, followed by exact saved price/quantity checks.
- Bulk export-format CSV multipart preview and reviewed bulk save, with no
  writes during preview and exact persistence checks.
- Legacy sheet CSV multipart preview, with no new saved sheet.

Both isolated HTTP and HTTPS are mandatory. Real Chromium uses its installed
same-origin fetch wrapper to add \`X-Tracker-CSRF\` for URL-encoded and multipart
writes. Negative requests originate outside that wrapper using the
Playwright API context and must fail 403. Positive responses must report a
valid CSRF token, the originating request header must match the browser
token, and the original pre-redirect route response status must be correct.

All direct SQLite reads are constrained to the guarded disposable
\`/tmp/tracker-browser-qa.*\` database; no installed database is used.
The four-worker isolated Chromium limit remains in place after the previous
OOM fix. Existing app routes, release guard, session isolation and
production CSRF configuration are unchanged.

Assuming the unchanged 144 unsafe-route ledger, expected source-only
readiness is **77 source-witness candidates** and **67 remaining**,
with **64 explicit full-browser witness manifest routes**. This is
a source inventory, not execution evidence and not global strict-CSRF
authorization. Full guarded DEV qualification and standard exact-commit
promotion are still mandatory.

Other non-vendor unsafe routes, session/account isolation review,
and the larger global CSRF readiness process remain out of scope.
