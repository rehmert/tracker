# Multiple destination vials — Tracker Blends

The read-only reconstitution planner now accepts **Maximum destination vials** and **Capacity per destination vial**. It maximizes complete draws subject to source inventory and total capacity, then displays a vial-by-vial fill plan. It fills earlier destination vials first (whole draws only). It does not save, reconstitute, or change inventory.

The physical blend recording form accepts **Number of destination vials** (1–100). Enter total measured source transfers and total additional diluent for the whole batch. The recording transaction creates that many separately tracked blends, divides each source transfer and diluent equally between them, and deducts the total source transfer once. Each resulting destination vial has its own label (`Label (1/N)`, etc.), volume, components, and administration history. The per-vial capacity validation applies to each destination.

**Important:** The what-if planner's fill-first distribution (e.g. 7 draws in vial 1, 3 in vial 2) differs from the recording form's equal-split distribution (5 and 5). The planner is not an executable preparation plan. Enter only actual measured transfer quantities in the recording form; it records equal aliquots. Do not use the form for unequal destination fills. No database migration is required.

This is inventory arithmetic, not a verification of compatibility, sterility, source-vial physical capacity, stability, or clinical dosing.
