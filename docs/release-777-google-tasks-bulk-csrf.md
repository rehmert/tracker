# Release 777 — Google Tasks bulk title form accepts Tracker CSRF metadata

Baseline: DEV Release 776 at `03e4f6f644566bb270d0027a369083972820a602`. PROD stays on 773
pending separate explicit promotion of Releases 774–777.

The Tracker browser-side form enhancer automatically attaches a hidden
`csrf_token` field to every POST form. Release 774's strict bulk-title
validator mistakenly rejected that known security field as an unknown title.
The visible symptom was HTTP 400 `Unexpected Google Tasks title field`
when the user pressed **Save all titles** from a real browser, while
synthetic server-only tests passed because they omitted the field.

Fix: the bulk-title route recognizes exactly one `csrf_token` metadata
field (the name comes from `app.csrf_runtime.FIELD_NAME`) and leaves CSRF
authentication and verification with Tracker's existing middleware.
The route still rejects duplicate security fields, unknown or duplicated
title fields, malformed/overlong titles, and stale source lists. All title
changes remain a single atomic transaction. The Google API, task identities,
title lengths, scheduled times, projections, notes, and medication/protocol
data remain unchanged.

Regression tests simulate the real browser's hidden form field alongside
multiple title edits; assert success, atomic rejection of duplicates or
unknown fields, and compatibility with the existing CSRF injection contract.
No schema, dependency, OAuth or deployment changes.
