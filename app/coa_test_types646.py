"""Release 646: common COA document test types, grouped for a compact select.

Categories synthesized from published Janoshik, Freedom Diagnostics, ILS Labs
and Vanguard testing service menus (November 2026). These are *test labels*,
not a claim that any individual sample has passed the selected analysis.

Sources:
https://help.janoshik.com/article/24-what-are-additional-services
https://freedomdiagnosticstesting.com/
https://ils-lab.com/services/peptide-testing/
https://vanguardlaboratory.com/peptide-testing/
"""

COA_TEST_TYPE_GROUPS = (
    ("Core analysis", (
        ("Purity", "Purity (HPLC)"),
        ("Identity", "Identity (LC-MS / HPLC)"),
        ("Purity & identity", "Purity + identity"),
        ("Net peptide content", "Net peptide content (CHNS / assay)"),
        ("Potency / content", "Potency / amount (mg per vial)"),
        ("Concentration", "Concentration / strength (mg/mL)"),
        ("Conformity / variance", "Conformity / batch uniformity"),
    )),
    ("Safety & contamination", (
        ("Endotoxin", "Endotoxins (LAL / USP 85)"),
        ("Sterility", "Sterility (USP 71)"),
        ("Microbial screening", "Microbial screening (PCR / DNA)"),
        ("Bioburden", "Bioburden (TAMC / TYMC)"),
        ("Heavy metals", "Heavy metals (ICP-MS)"),
        ("Fentanyl", "Fentanyl screening"),
        ("Residual solvents", "Residual solvents (GC-MS)"),
    )),
    ("Specialized analysis", (
        ("TFA", "TFA / trifluoroacetate"),
        ("pH", "pH measurement"),
        ("CHNS", "CHNS / elemental composition"),
        ("LC-MS", "LC-MS contamination screening"),
        ("GC-MS", "GC-MS contamination screening"),
        ("HGH dimer", "HGH dimers / aggregates"),
        ("BA/BB", "Benzyl alcohol / benzoate (oil)"),
        ("Counterions", "Counterion analysis"),
        ("Stability", "Stability / degradation"),
        ("Full QC panel", "Combined QC panel / multiple tests"),
    )),
)

COA_TEST_TYPE_VALUES = frozenset(value for _, options in COA_TEST_TYPE_GROUPS for value, _ in options)
COA_CUSTOM_TYPE_SENTINEL = "__custom__"
