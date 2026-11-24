# Release 765 — Mobile daily action handoffs (Phase 1)

Baseline: installed DEV and PROD Release 764,
`1b72897158aa91aa6f2de6eda2908ae4b9e4d366`.

## Change

- Keep one existing Today recording bar, Today schedule, vitals form,
  food/workout summaries, and Quick Entry. Do not add duplicate forms.
- Insert one compact, conditionally visible **Needs Attention** section
  above the Today command-center summaries. Counts are based on the
  current scoped workspace records; the section is omitted when clear.
- Due administrations link to the existing per-item scheduled dose actions.
- Missing-COA count exactly matches Dashboard and the server-filtered
  Vials inventory, including finished vials, excluding discarded vials,
  recognizing both legacy direct and many-to-many COA associations.
- Vials with passed dates link to the filtered inventory-date review,
  and up to four *specific affected* vial records are directly linked.
  The list uses the same active/closed/date eligibility as the existing
  daily summary, which may differ from nonempty FEFO-only review counts.
- Active protocols missing start dates now have exact-record edit
  links, instead of just a generic Protocols manager link.
- Dashboard due/status attention links open the actionable Today
  schedule; missing-start attention opens the Today specific record list;
  the at-a-glance no-COA metric opens the existing exact filtered Vials list.
- Mobile tap targets are at least 44px, focus indication is visible,
  and 320–430px layouts avoid fixed minimum widths.

## Safety

No DB schema changes or record writes. No saved priorities or browser
storage. No user records in GitHub. All reads use get_scoped_db390.
Existing dose, food, vitals, inventory, schedule, history, and
permission semantics are unmodified. Existing release receipt/agent
protocol and explicit PROD approval boundary remain intact.

Changed-scope qualification includes synthetic ORM/route tests,
Jinja/Python/bash syntax, mobile layout contract checks, 509/695
Today regressions, 761 Vials filtering, and Dashboard schedule tests.
