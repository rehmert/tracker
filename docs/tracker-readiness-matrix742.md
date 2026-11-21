# Tracker Release 742 remaining issue acceptance status

| Initiative | Added in 742 | Remains blocked until |
| --- | --- | --- |
| Strict global CSRF (#9) | Current unsafe-route scanner, explicit newer MACD writes, fail-closed readiness command | Complete signed-positive/unsigned-negative strict HTTP+HTTPS native, multipart, JS/HTMX and manual auth review; opt-in DEV rollout and rollback |
| Dependency reproducibility (#10) | Browser binary SHA/OS/libc path-free fingerprint, DEV/PROD parity and private no-clobber receipts | Approved wheel supply chain, browser/OS library evidence, full offline browser replay, tested rollback and separate dependency approval |
| Release agent catch-up (#11) | Receipt/ancestry verifier accepts different DEV install vs PROD bases only when each is valid; stale/duplicate/forged cases fail | Host-side release-event controller source fix, isolated controller integration, real approved catch-up preflight |
| CSS/mobile consolidation (#54) | One fewer global CSS request; original 676 + 679 rule order unchanged with Chromium computed parity | System-wide CSS coverage and safe retirement of remaining duplicates, full live-phone UX assessment |
| System MACD (#56) | No new destructive mutations in 742; keep Release 741 safety | Continue owner-scoped module-specific real workflow verification and separate scoped follow-up defects |

No approval for PROD, global CSRF enforcement, dependency upgrades, bypass
of historical records or release-agent policy changes is implied.
