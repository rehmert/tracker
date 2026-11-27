# Release 805: section navigation reliability

Native expandable sections now refresh the existing Jump to Section and Copy Section Link controls when opened or closed, including nested disclosures. Both controls use matching visibility rules, preserve existing IDs, and batch repeated HTMX refresh events. The page-jump list also refreshes on browser history restoration. No new navigation widgets, storage, database, endpoints, or dependencies. Acceptance: expand and collapse sections on long pages, verify the section list updates, and verify existing anchors and links remain usable.
