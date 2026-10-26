# Bulk Purchase UX update

- On each purchase, add a supply with **Packages** (default) and enter number of packages, units per package and **total line price** from the retailer order summary. The form previews individual units, subtotal and per-unit cost.
- Choose **Individual units** for unboxed purchases; the old per-unit pricing remains supported.
- Existing product configurations are offered in a product selector; new bulk purchases save/update reusable defaults in `supply_products`. Legacy supply names are also offered for convenience.
- Edit items using the same layout; usage history and manual adjustments remain intact, and quantities cannot be reduced below recorded usage.
- Supplies page links to orders for purchase entry. Stock and usage tracking remain on Supplies.
- Existing bulk and individual purchase records are unchanged. A new `supply_products` table is created by `Base.metadata.create_all` at startup. No destructive migration.
- Deploy preserving `.env`, `data/` and uploads; restart `tracker.service` and hard-refresh browser.
