# Release 752 — All active protocol inventory forecast + CSRF maintenance

Base: DEV-installed, qualified Release 751
f495d0f9686a24403f874f932e34a5039a186dce.

The dashboard now iterates every active protocol item instead of only
stocked compound keys. A row with a protocol link is visible for missing
inventory, missing start dates, future stages, ended stages, invalid
frequencies, and active protocols without items. Inactive what-if plans
remain excluded. For current-stage items sharing one compound/dimension,
their rates combine against the same available stock. Low-stock alerts
and watch cards are deduplicated for shared stock. No depletion date is
invented for stages that are not current. This is approximate and does
not model future schedule changes, transfers, or purchases.

The tracked CSRF activation helper now accepts the original session-auth
303 health redirect to /login without following it to an HTML 200 page,
and retries transient service startup errors for up to 45 attempts after
service restarts, including enable, disable, and rollback. The original
unsigned-write 403 probe, flag checking, and rollback controls remain.

Change-scoped tests cover dashboard math, protocol inclusion, staging,
no-stock alerts, template/route wiring, and helper invariants plus
legacy Release 751 CSRF and receipt tests. No data/schema migration.
Strict CSRF already active on DEV remains enabled during deployment.
PROD promotion requires explicit authorization.
