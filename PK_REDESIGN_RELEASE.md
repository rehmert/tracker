# PK Simulator workflow redesign — 2026-10-30

Three guided modes: Protocol, Custom, Compare. Existing graph, scenario, comparison, overlay, and scenario management endpoints remain. Advanced assumptions are collapsed; chart is prominent, includes a window selector, summary metrics, PNG and CSV export, and context-sensitive help.

New model recognition: liraglutide (human SC elimination ~13h) and immediate-release exenatide (human SC elimination ~2.4h). Semaglutide (injectable, ~168h) was already supported. Absorption constants are illustrative, not fitted concentration curves. Extended-release exenatide is excluded.

Sources:
- https://www.accessdata.fda.gov/drugsatfda_docs/label/2026/209637s038lbl.pdf
- https://www.accessdata.fda.gov/drugsatfda_docs/label/2025/022341s042lbl.pdf
- https://www.dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=e6cb5c8f-e97f-4a6a-95a4-939fd2393949

Cautions: Peak/trough summary is computed from visible sampled points, not continuous extrema. BPC-157 still requires user-entered assumptions. Short-lived compounds retain the 24h past / 48h future graph limit in the backend. This is a research-oriented, non-clinical model.
