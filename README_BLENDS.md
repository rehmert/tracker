# Multi-peptide blend inventory (recordkeeping)

The **Blends** menu records transfer of 2–8 distinct peptide compounds into a separate physical destination vial. This is **not** a preparation protocol, compatibility endorsement, sterility assurance, or dose recommendation.

- Enter source vials, the amount of each compound actually transferred, and your own target amount of each compound per draw.
- The form calculates transferred solution volume from the existing source vial concentration, adds the entered diluent volume, and checks optional destination capacity.
- For a source vial without a recorded liquid volume, the entire remaining content must be transferred; its powder contributes zero *recorded* liquid volume. This is an approximation, not a displacement measurement.
- A single draw has a fixed composition. If user-entered target amounts imply different draw volumes, creation is rejected. No ratio or dose is chosen by Tracker.
- Source inventory is reduced by transfer ledger entries. These are **not** administration records. Source vials fully transferred are marked finished.
- Blend doses and discarded draws are recorded under **Blends → [blend]**, separately from the ordinary single-compound dose log, with the quantity of each constituent calculated from draw volume. These entries are not yet included in protocol adherence, PK Simulator, Overview administration totals, or the single-compound dose log.
- This first version does not support editing or reversing transfers or draws; correct mistakes by restoring a backup rather than deleting source rows manually. Confirm all values before saving.
- If a source was already partly administered, only the remaining content may be transferred. Mixing the same compound from two separate source vials in one blend is not supported yet.
- Diluent is recorded as volume but **not deducted from BAC-water supply inventory**. Record any supply consumption separately.
- Do not change the original source vial's total content or recorded volume after transfer; it would invalidate historical transfer assumptions.

Schema: `blends`, `blend_components`, `blend_doses` created by `Base.metadata.create_all` at startup. No alteration to existing tables. Existing data is not rewritten.

Install: stop service, make a consistent full backup (including data and .env), unzip patch into `/opt/tracker`, restore app file ownership, start service. The new tables are created automatically.
