# Purchases: mixed vial, supply and pill orders

- Purchase detail now supports adding BAC water and pills alongside vials, under the same vendor/order/date.
- Purchase list shows both vial count and supply/pill line count.
- Purchase detail displays each supply line, remaining inventory, line subtotal and allocated landed cost.
- Purchase totals and vial landed costs allocate shipping, tax and discount across *all* items in an order. This may change previously displayed per-vial landed cost on mixed orders, correcting the earlier omission of supply lines.
- Supply/pill entries created from Purchases also appear in Supplies and share its usage tracking.
- Purchase deletion is blocked while vials, supplies or pills remain attached.
- Supply prices are **per mL** for BAC water and **per pill/capsule** for oral inventory; quantity is total mL or pill count.
- No schema migration required: existing `supplies.purchase_id` is reused.

## Deployment
Back up the database and uploaded files; deploy the application while preserving `.env` and `data/`. Restart the service and hard-refresh the browser.
