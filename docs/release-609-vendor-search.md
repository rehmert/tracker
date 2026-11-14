# Release 609 — Vendor Price Comparison name search

Base: qualified DEV/PROD Release 608 `906d3e7515eea3829a81aff9528d55024025e7bc`.

## Change
Add a screen-only vendor-name search field adjacent to the compound selector
on Vendor Price Comparison. Matching is case-insensitive, trims surrounding
whitespace, and combines with the compound filter. It operates on every
original offer row regardless of current page. Typing resets to page one;
existing pagination and cross-page column sorting still work. A missing match
renders the existing empty-range indicator. No network request, server-side
query, database write, new endpoint, or stored preference is introduced.

## Qualification
The real inline script is exercised by isolated Chromium in
`tests/test_release605_vendor_label_ux.py`, including 320/390/1024px
viewports, combined compound/vendor filtering, empty results, retained
sorting and pagination, and label zoom. The standard complete guarded DEV
qualification remains mandatory, followed by manual UI acceptance, the
read-only signed PROD promotion preflight and explicit approval. Do not use
GitHub Actions to deploy.

## Preserved constraints
The installed deployment runner retains 16 pytest workers with
`--dist=loadfile`, a 16 GiB systemd worker memory limit, full test
coverage, isolated browser checks, backup/restore, SHA pinning, signed
promotion and rollback. No runtime dependency or schema changes.
