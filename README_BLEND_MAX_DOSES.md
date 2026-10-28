# Blend planner: maximize complete draws (Option 1)

The reconstitution what-if now derives peptide transfer quantities from source remaining content, user-entered target doses, desired draw volume, and destination capacity. No transfer amounts are required for the what-if calculation.

Algorithm: complete draws = min(floor(capacity/draw_ml), floor(remaining_compound_i/target_i) for each peptide). Each transfer = complete_draws * target_i. Final blend volume = complete_draws * draw_ml. Equal source withdrawal allocation is an illustrative assumption, not a uniquely determined or validated preparation volume. Already-liquid sources use their recorded concentration. Manual source BAC mode is retained.

The planner does not save inventory changes. The existing Record blend operation still requires manually entered measured transfer amounts and previously reconstituted sources. No database changes.

Theoretical volumes assume additive liquids and ignore powder displacement, headspace, dead volume, stability, sterility, solubility and compatibility.
