# Release 522 — fix legitimate Vitals writes behind LAN TLS proxy

Base: DEV-qualified Release 521
`7f1159270cc9624d757ade540aa576e46fc91d89`.

## Production symptom and root cause

An authenticated user reported `Cross-origin write request denied.` when
saving a Vital in PROD. The legacy HTTP middleware compares the browser's
public `Origin` against the request `Host` seen by FastAPI. A TLS
terminating reverse proxy is permitted to rewrite `Host` to an internal
listener, making an **otherwise same-origin** browser POST fail before the
Vitals route gets control. An earlier release had already added a signed
proxy-origin exception just for Food; Vitals, Labs and COA were excluded.

A production request-header capture has **not** yet confirmed the exact
Origin/Host mismatch; this release tests and fixes that concrete likely
failure mode and will require a real PROD smoke check after deployment.

## Fix

- Keep `TRACKER_ORIGIN_GUARD=1`. Do not blindly trust
  `X-Forwarded-Host` or disable origin checking.
- If the ordinary origin check rejects a write, allow a proxy-aware fallback
  only when all of the following are true:
  - `Sec-Fetch-Site` is exactly `same-origin` (not `same-site` or
    `cross-site`);
  - `Origin` is a syntactically valid HTTP(S) origin or exactly `null`;
    reject duplicated/malformed Origin and duplicated CSRF headers;
  - a valid server-signed CSRF cookie/submission pair has been verified.
- Valid headers or small URL-encoded native form fields are authenticated
  in the existing middleware before the proxy exception can apply.
- For native `multipart/form-data` forms with no CSRF request header,
  middleware only marks an explicit **must-verify-at-route** state. The
  existing FastAPI route dependency then checks precisely one signed
  `csrf_token` field against its cookie *before* executing an endpoint.
  The proxy exception never reads/uploads file streams in HTTP middleware,
  and never treats an unverified multipart form as authorized.
- Unsigned writes, forged tokens, cross-site/same-site writes and malformed
  origins remain denied. Authentication and user-specific authorization are
  still mandatory. Requests without a browser Origin retain prior behavior.
- Keep `TRACKER_CSRF_ENFORCE=0` globally by default. The proxy exception
  nevertheless requires **verified signed CSRF** for every recovered write,
  whether or not global strict mode is on.

## Regression coverage

- `tests/test_proxy_origin522.py` exercises the real Tracker middleware
  with a TestClient whose upstream `Host` is internal and whose browser
  `Origin` is public/HTTPS or opaque. Checks real Vitals create/edit/delete,
  form/header tokens, missing/forged token rejection, no unintended mutation,
  Fetch Metadata, malformed/duplicated headers, and real multipart Labs
  verification in report-only mode.
- `scripts/tracker-tls-proxy501.py --qa-rewrite-browser-host` simulates the
  production behavior **only** for Vitals, Labs and COA mutation routes on the
  already-existing loopback-only disposable Chromium QA proxy.
- `tests/browser/test_vitals_proxy_host522.py` runs real Chromium native
  HTTPS Vitals create, edit, and HTMX delete, verifies browser Origin and
  same-origin metadata and rejects unsigned/cross-site POSTs.
- Existing Releases 501/521 real Chromium Labs and COA multipart tests are
  automatically rerun through the rewritten-host fixture, including the
  global strict-CSRF second pass. The release 521 dual-pass qualification
  inventory remains complete.
- The legacy Food-specific contract test is updated to reflect the new
  shared signed same-origin fallback while asserting unsigned/cross-site
  requests stay blocked.

## Deployment and verification

GitHub is source control only. No hosted tests, new packages, migrations,
schema/model changes, systemd changes or production proxy changes.

1. Pin this branch to a DEV release from the exact 521 SHA.
2. Require both browser passes (including rewritten Host for Vitals/Labs/COA),
   the entire backend suite, and isolated backup/restore. Require
   `EXIT_STATUS=0` and live DEV runtime smoke.
3. Only after qualified DEV may the exact commit be promoted to main and
   deployed to PROD. PROD currently reports running Release 520, so a
   guarded PROD upgrade must pin its actual verified starting SHA and not
   assume Release 521 is already installed there.
4. Verify a real Vitals create, edit, and delete through the production
   LAN URL after deployment. If it still returns 403, capture **nonsecret**
   request metadata at the proxy: whether public Origin is normal/null,
   the upstream Host, and the `Sec-Fetch-Site` classification; never log
   token, Cookie, credentials or form data.

### Limitations

A browser or reverse proxy that strips `Sec-Fetch-Site`, or never issues a
signed form token, still fails closed. Such an environment should have its
proxy configuration corrected (preserve public Host/Origin) rather than
globally disabling the origin guard.
