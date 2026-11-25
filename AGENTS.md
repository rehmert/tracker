# Tracker development conventions

## Action controls (standing UI requirement)

Every user-facing action must look like a button. Do not place raw text links or badge/tag-styled links next to action buttons. Use the established `tracker-ui-action` primitive (and `tracker-ui-action--primary` for the primary action), or the existing equivalent action-button component used by the surrounding workflow. Do not create a new competing visual style.

- Keep GET/navigation actions as semantic anchors styled as buttons. Keep submit, edit-in-place, delete, and other mutations as native buttons in their existing forms.
- Adjacent actions must share consistent dimensions, border, radius, typography and alignment. Preserve a clear primary/secondary hierarchy and mobile tap targets; respect compact layout preferences.
- Plain links are appropriate for inline references or ordinary navigation, not task controls. Status badges are informational, not actions.
- When touching a workflow, inspect neighboring actions and normalize inconsistent controls in that scope. Validate rendered desktop and mobile controls, not just class names.

Use the established exact-SHA DEV-first release workflow and change-scoped tests. Never promote to PROD without explicit authorization.
