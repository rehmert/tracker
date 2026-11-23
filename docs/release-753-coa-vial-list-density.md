# Release 753 — Compact COA list and simplified vial list

Based on installed and DEV-qualified Release 752:
fd2d92c89b285a0f7871866d3da20f7a302da72d.

COA list actions previously rendered three full-size MACD buttons that could
wrap and make every row much taller. Replace them with short inline
Edit / Docs / Vials links, retaining all three destinations and providing
descriptive accessible labels and visible keyboard focus. The link row
does not wrap, including on phone-width layouts.

The Vials table already links the vial number/label to its detail page,
where the original Edit vial action remains. Remove the duplicate Edit
control from every vial list row without altering forms, vial history,
stock calculations, selection, sorting, or bulk management.

Scope: templates and an isolated stylesheet only, plus targeted tests.
No database/schema, API, security, or authentication changes. Validate
desktop/mobile browser layout, original route destinations, functional
GET rendering, and prior UI MACD regression contracts. Keep the full
suite skipped for a narrow UI release unless explicitly required.
No PROD deployment without a separate user authorization.
