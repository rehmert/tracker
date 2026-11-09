# Release 517 — outbound URL hardening (CSRF staged separately)

Base: Release 516 source candidate `a18ee9816862b09f992a20074276e9af902198a8`.

## Security change
`app/vendor_url_extract.py` now verifies public DNS answers once per
redirect hop and connects only to a selected vetted literal public IP.
The socket connection never repeats DNS lookup for the untrusted hostname.
HTTPS retains system-trusted certificate validation and hostname/SNI checks
against the URL's original host. HTTP proxy settings are not consulted;
redirects have a four-hop ceiling, each new hostname is independently
validated, and response bodies are bounded to 2 MiB.

This fixes a time-of-check/time-of-use DNS-rebinding gap in the prior URL
previewer. It does not guarantee that a firewall or upstream service can
never be misconfigured, and it does not protect general-purpose code outside
this preview helper.

## CSRF rollout remains gated
Do NOT set `TRACKER_CSRF_ENFORCE=1` merely because this release is installed.
The legacy application still reports CSRF for some multipart/browser forms
without verifying their request bodies. Strict mode must be qualified
across all authenticated forms and uploads on the DEV LXC before default
enforcement can safely be changed. See issue #9 and the existing
`scripts/tracker-csrf-readiness.py` source inventory. Existing mandatory
signed CSRF checks for login/secondary routes remain unchanged.

## Isolated qualification
`tests/test_release517_vendor_egress.py` uses mocked DNS, sockets, TLS and
upstream responses, never a real external connection or user data.

After verified Release 516 on DEV, require the *complete* guarded DEV release
suite plus manual acceptance of the optional vendor URL preview if used.
Do not merge/promote until successful DEV LXC qualification
(`EXIT_STATUS=0`). No GitHub-hosted testing.
