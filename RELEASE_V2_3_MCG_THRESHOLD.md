# v2.3 — mcg-to-mg display threshold

Shared mass-quantity formatting (`app.units.fmt_amount`, used by the `amt` Jinja filter) now displays quantities as mcg through and including 100,000 mcg; above that, as mg until the existing 1,000,000 mcg threshold for g. Thousands separators remain enabled. Decimal conversion uses Decimal(str(value)) to preserve displayed sub-mg precision. Negative values use the absolute-value threshold. Stored base units, editable inputs, concentrations, CSV outputs, and arithmetic are unchanged. This is a display-only update and requires no migration.

Examples: 2,500 mcg; 100,000 mcg; 100.001 mg; 125 mg; 1.25 g.

Validation: 22 targeted tests passed. The full regression run did not complete within the execution window.
