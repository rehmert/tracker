# Reconstitution-first blend planner correction

Each dry source vial is reconstituted in full before any solution is withdrawn. For a dry source, the planned withdrawal volume is `BAC added to entire source vial × peptide amount transferred / peptide remaining in source`. The rest stays in that source vial. Already-liquid sources use their recorded concentration. The planner adds all withdrawals and calculates additional destination diluent, while enforcing destination capacity and fixed peptide ratios. This is a read-only what-if calculation.

The actual blend-save and basic blend-preview endpoints now reject unreconstituted dry sources. Record reconstitution in the vial workflow first; then record the blend transfer. The planner does not perform the reconstitution or deduct inventory.

Calculations assume homogeneous solution and additive nominal liquid volumes; they do not establish sterility, solubility, chemical compatibility, stability, or safe administration.
