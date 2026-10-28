# Blend reconstitution calculator — automatic allocation

The What-If calculator accepts the desired draw volume and per-peptide targets.
It computes required final volume for each peptide and rejects inconsistent ratios.

Automatic allocation (default): already-liquid sources contribute their fixed transfer
volumes; remaining final volume is divided equally among dry-source withdrawals.
Each dry source is assumed fully reconstituted before the specified portion is
withdrawn, so source BAC = allocated withdrawal * source remaining content /
peptide content transferred. This is one mathematically valid allocation, not a
unique solution or a recommendation about physical preparation.

Manual allocation preserves the previous behavior: user-entered BAC volumes for
source vials, and the remaining liquid volume is assigned to the destination.

No inventory is changed by preview. No schema migration is required. Actual blend
recording still requires separate, already-reconstituted source vials.

IMPORTANT: This arithmetic does not establish chemical compatibility, solubility,
sterility, stability, safe reconstitution volumes, powder displacement, dead space,
or suitability for injection. Confirm practical source vial capacities independently.
