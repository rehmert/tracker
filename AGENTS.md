# Tracker development conventions

## Action controls (standing UI requirement)

Every user-facing action must look like a button. Do not place raw text links or badge/tag-styled links next to action buttons. Use the established `tracker-ui-action` primitive (and `tracker-ui-action--primary` for the primary action), or the existing equivalent action-button component used by the surrounding workflow. Do not create a new competing visual style.

- Keep GET/navigation actions as semantic anchors styled as buttons. Keep submit, edit-in-place, delete, and other mutations as native buttons in their existing forms.
- Adjacent actions must share consistent dimensions, border, radius, typography and alignment. Preserve a clear primary/secondary hierarchy and mobile tap targets; respect compact layout preferences.
- Plain links are appropriate for inline references or ordinary navigation, not task controls. Status badges are informational, not actions.
- When touching a workflow, inspect neighboring actions and normalize inconsistent controls in that scope. Validate rendered desktop and mobile controls, not just class names.

Use the established exact-SHA DEV-first release workflow and change-scoped tests. Never promote to PROD without explicit authorization.

## Daily UX and mobile contract (Release 790)

- One authoritative schedule projection and reconciliation path; Today, Dashboard and Calendar must agree. Use the same scheduled-dose form from every entry point, preserve the originating context, and never assume an ambiguous inventory source.
- Default to daily tasks, not administrative tools. Keep historical and advanced tools reachable by stable links, search and disclosures.
- Populate known fields, keep optional fields collapsed, and use one explicit Save action for routine recording. Do not add redundant confirmation gates. Retain genuine validation, duplicate prevention, inventory safeguards and destructive-action review.
- Use shared Jinja action/submit components, consistent chevrons, accessible names, keyboard focus, responsive 44px touch targets and matching primary/secondary controls. Keep native GET links and POST forms.
- Preserve date, search/filter context and relevant return anchors after saves. Prefer batch editing for multiple independent changes; no implicit batch recording.
- Use 24-hour time and accept colonless HHMM where supported. Keep recent lists short with access to full history. Make pending vs recorded state explicit.
- Validate actual rendered desktop and mobile workflows, not just CSS class presence. Do not introduce global styling overrides to fix one page.

- Action collections must use available horizontal space: compact responsive grids or wrapping rows, never a full-width vertical stack when multiple controls fit. Test rendered button positions at desktop and phone widths, including compact density. Collapse long explanatory copy to one line with an accessible More/Less disclosure while preserving its full text.
