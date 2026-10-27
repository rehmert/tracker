# Blend reconstitution what-if planner

The Blends page now includes a read-only reconstitution calculator. For each dry source vial, enter the BAC water volume you are considering; for already liquid source vials use 0. Enter the amount transferred and the target amount per draw for each peptide, plus a desired draw volume and destination capacity (default 3 mL).

The planner calculates the required total volume for the requested targets, the source liquid volume, additional diluent volume needed in the destination, concentration and amount per draw, and unused nominal cartridge capacity. It refuses incompatible peptide ratios, insufficient source inventory, impossible volumes, and over-capacity plans.

**Preview does not save or transfer anything.** To execute a plan, record actual source reconstitutions in the existing vial workflow and then use the existing blend creation form with actual measured volumes. The planner does not prescribe reconstitution, confirm peptide compatibility, sterility, solubility, or account for powder displacement, syringe dead space, or required cartridge headspace. Use manufacturer/clinician guidance for actual preparation.

Install the small patch over the latest Tracker version; no schema migration is needed.
