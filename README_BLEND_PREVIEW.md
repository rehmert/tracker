Blend what-if preview patch

Adds POST /blends/preview and a Preview blend button. The preview reuses the exact validation and arithmetic of the save route but does not commit any changes. No database migration required.

Install: stop tracker, back up /opt/tracker, unzip over /opt/tracker, restart tracker.

Tests: 151 passed, 1 pre-existing unrelated protocol-title assertion failure.
