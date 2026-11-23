# Release 761: Dashboard missing-COA drilldown

The dashboard's "N vials without COAs" attention item used to link to
the general COA manager. It now opens the Vials inventory table with
"Missing COA" selected and a visible "Not discarded" status scope.

The status scope deliberately matches the dashboard count definition:
all vials except discarded, including finished vials, with no COA
through either the legacy COA foreign key or the modern linked-COA
association. The Vials table's COA indicator now uses the same combined
definition. Query filtering executes server-side. It never changes
inventory or certificate records.

The vial page exposes a COA filter alongside compound and status, a
visible filtered count and a clear action, and preserves the filter
through status, compound and browser-local saved views.

No migrations, record updates, or logging changes. Scoped tests cover
both association types, missing records across statuses, compound
filtering, user interface wiring and read-only behavior. Only DEV
qualification and install are authorized automatically; PROD needs
separate explicit user approval.
