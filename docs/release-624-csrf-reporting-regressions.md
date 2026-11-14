# Release 624 — CSRF reporting boundary regression

Base: Release 623, commit `3adce75122af6f8b01af50921c31f1209c7fbefe`.

Release 624 adds deterministic unit tests of the existing report-only CSRF
inspection path. It checks that multipart bodies are not read by the reporting
middleware, duplicate or blank CSRF headers are rejected as invalid, URL
encoded duplicate tokens are invalid, header precedence cannot fall back
to fields, oversized bodies are left uninspected, and GET never consumes a
write body. These are existing reporting semantics; no enforcement change.

The tests make no assertion that uninspected multipart submissions are
protected. They are **not** substitutes for isolated HTTP/HTTPS browser
tests with real CSRF/session credentials and real form submissions.

The next Phase 1 work must identify representative legacy multipart and
native controls and add authenticated negative browser tests, followed by
per-endpoint form-bound protection where the evidence warrants it.

No runtime app files, route handlers, dependencies, schema, release runner,
origin checks, or default CSRF policy are modified. Maintain 16-worker full
suite, isolated HTTP/HTTPS browser gates, immutable receipts, signed release
promotion and distinct DEV/PROD approvals.
