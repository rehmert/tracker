# Release 612 — Resume held Release 610 vendor filter reset

**Base:** DEV/PROD-qualified Release 611, `f635cda98c5753e544d74748631ad9e2b5a2169f`.
**Ported source:** Held Release 610 candidate, `a10f551ec243a13f1567236762e51ebdb1ae5306`.
**Release 610:** Never deployed; keep it as historical held work. Release 612 is a distinct qualification.

## User-facing improvement

Vendor Price Comparison gains a **Clear filters** button. When the compound
selector, vendor-name search, or page-size selection differs from defaults,
the button is enabled. Clicking it clears both filters, restores 25 offers
per page and page one, updates the matching-offer indicator, and returns
keyboard focus to the vendor-name search. Existing sort order stays intact.
The button is disabled again when filters and page size are at defaults.

The Release 610 markup and Chromium regression test files were ported
byte-for-byte onto the Release 611 baseline; the integrated regression checks
reset under combined filters, search, page-size changes, mobile widths, and
keyboard focus. The Release 611 blend-dose Calendar, Dose Log and navigation
fixes remain present because this branch starts from Release 611.

No schema, authentication, routing, server API, inventory, or persistence
changes. No additional network requests.

## Qualification and promotion

Run exact-commit guarded DEV deployment (the complete focused, Chromium
HTTP/HTTPS, strict-CSRF, backend and restore checks) and verify the root-only
qualification receipt. Then visually review vendor filter reset on DEV.
Use the read-only signed promotion preflight, followed by explicit
`--execute` approval only after acceptance.

**Resource contract:** 16 backend pytest workers with
`--dist=loadfile`; transient systemd `MemoryMax=16G`.
