# Stage 27 — Legacy vendor-price CSV compatibility

- Bulk export/import now permits empty content amount and unit only for an existing legacy offer whose stored structured content is also unknown.
- Existing legacy strength labels remain unchanged when the structured content is unknown.
- New offers still require valid per-vial content, and known values cannot be erased through blank CSV cells.
- No schema changes; no automatic data corrections.
- Tests: `PYTHONPATH=. python -m pytest -q tests` — 221 passed in the supplied combined working tree.
