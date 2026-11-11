# Release 562 — Blend preview and compact vial selector

- The Preview blend button uses the read-only reconstitution what-if calculation when source vials are dry or measured transfer amounts have not been supplied. It cannot enable Record for such a hypothetical preview.
- For liquid sources with positive measured transfers, the existing read-only blend preview is used, enabling Record only on a successful preview of unchanged inputs.
- Validation errors from both preview endpoints are displayed in full, rather than replaced by a generic message.
- Source selection headers and input widths are compact. Dropdown labels read `#ID · abbreviated compound · purchase vendor · lot · quantity unit`, without the word “remaining”. Source option value remains the vial database ID.
- No changes to inventory deductions, write endpoints, database schema, or dosing calculations.

Known compounds are abbreviated to recognisable short names (for example Tirzepatide → Tirz, Retatrutide → Reta, Tesamorelin → Tesa, Ipamorelin → Ipa). Unknown compound names are shortened to at most 12 characters. The underlying compound name and vial ID are not changed.
