# Release 764 — Keep registered compound names in authored title casing

Parent: installed DEV/PROD Release 763, 99e10eef2125e74b4315f3ee89dc546ae22d7524.

The global page-title-case script applied generic Title Case to all headings
and document tab titles, changing scientific and user-defined compound names.

A read-only, private/no-store endpoint at /compounds/title-names reads compound
names from the current user's scoped workspace. The client loads these names
before applying capitalization, and **exempts the entire title** when a full,
case-insensitive compound name is present. Hyphens, digits, spaces and
case-sensitive notation remain untouched. Nested heading text is checked
together. Other headings continue normal title casing. Existing
data-no-title-case exceptions remain intact.

If the catalog is unavailable, the formatter fails closed: original title
text stays unchanged rather than risk corrupting a compound name. No stored
titles or records are rewritten, and no schema/data migration is required.

Focused qualification includes server-scoped catalog and private response,
actual Node VM execution of heading and document-title rules, existing
page/nav title regressions, and the shared impact preflight. DEV-first
install; PROD requires separate explicit authorization.
