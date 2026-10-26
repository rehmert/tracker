Dashboard customization fix
===========================

Fixes the Move Down action: using Element.after() instead of insertBefore() with a reference node that could be the moving element itself. Saved dashboard order now rehydrates in place instead of appending sections to the end of the page. Browser cache-busting version updated.

No database migration required. Existing localStorage preferences are retained.

Install: back up data; deploy files preserving .env, data, and uploads; restart tracker.service; hard-refresh browser.
