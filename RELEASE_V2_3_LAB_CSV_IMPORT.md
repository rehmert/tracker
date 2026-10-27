# Lab report CSV bulk import

- Create a lab report directly from a UTF-8 CSV using date drawn, lab, and notes.
- Bulk append CSV analytes to an existing report.
- Downloadable sample CSV at `/labs/csv-template`.
- Required columns: `analyte,value,unit`; optional: `ref_low,ref_high,note`. Header aliases supported.
- Empty lines ignored; ranges must have both endpoints or neither.
- Upload cap 2 MB / 2,000 results; reject malformed data atomically before database commit.
- Does not change existing results, tables, or database schema.
- No attached PDF/image is created from CSV.
