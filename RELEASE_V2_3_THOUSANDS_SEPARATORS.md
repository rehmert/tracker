# v2.3 — Thousands separators in displayed numeric values

- Shared numeric display (`num`, `amt`, `conc`, `signed_decimal`) now groups thousands with commas.
- Fixed-precision display (`n0`, `n1`, `signed`) now groups thousands. Existing currency format already grouped thousands.
- Inventory Intelligence depletion estimates use the shared grouped display.
- HTML `type=number` values use the separate `num_input` filter without commas, preserving valid editable inputs.
- Calculations, stored numeric values, and CSV exports are unchanged.
- No database migration required.
