# Release 622 — JavaScript HTTP write-site inventory

Verified base: Release 621 at `35f98e0f2f5690c6324559e6b5320ac9c54babbd`.

This source-only, read-only audit increment supplements the Release 620
unsafe-route inventory and Release 621 native-form/HTMX crosswalk with
potential JavaScript request call sites in static JS and HTML templates.

### Run

```sh
/opt/tracker/.venv/bin/python /opt/tracker/scripts/tracker_csrf_js_inventory622.py
```

The command prints JSON; it does not create files or perform requests,
import Tracker, access databases, or modify services. It identifies
candidate `fetch(...)`, `xhr.open(...)`, and `htmx.ajax(...)` calls.
Same-line literal unsafe method values are shown as hints; unknown
method values remain UNKNOWN. **Every result needs manual review**.

This is not a complete JS parser. Calls via wrappers, aliases, libraries,
templating, dynamic configurations or multiline code can be missed; comments
and strings can produce false positives. No matched or unmatched entry
proves effective CSRF protection or a vulnerability.

The full issue #9 acceptance still requires human route/form/JS review,
isolated HTTP and HTTPS browser proof, coverage of multipart and legacy
native forms, and separate DEV policy qualification before even considering
global strict-CSRF activation. Issue #10 remains open.

No changes to `app/main.py`, middleware, CSRF defaults, schema, installed
packages, or deployment scripts. The original guarded interactive DEV
qualification, 16-worker suite, and signed DEV-controlled PROD promotion
are required unchanged.
