# Release 759 — Consistent inventory mass display

Base: verified DEV-installed Release 758 (`6cf718ed0781fdbaa6ff350d782e5cc80758703d`).
The stored inventory and all runway calculations remain unchanged.

Inventory quantities are internally tracked as micrograms. The shared
mass formatter now displays **mg for magnitudes greater than 10,000 mcg**,
including multi-million-mcg inventory totals, without automatically
switching to grams. Values at or below 10,000 mcg remain in mcg.
For example, 36,349,664 mcg is shown as **36,349.664 mg**.

The dashboard inventory forecast previously bypassed the shared formatter;
its usable-stock cell now uses the same mass formatter. The dashboard's
current-protocol remaining-inventory cells also apply the formatter to
mcg-based items. Inventory Intelligence's remaining and historical-use
cells apply the same rule. IU and physical volume remain separate and do
not undergo mass conversions.

This is a display-only release: no schema changes, data rewrites, medication
or dose edits, concentration assumptions, or forecast arithmetic changes.
Qualification is change-scoped and guarded DEV-first. PROD needs separate
explicit authorization.
