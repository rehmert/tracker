# Bulk disposable purchases

Record supplies by **number of packages**, **usable units per package**, and **total line price**. For example, 2 boxes × 100 needles at $17.99 total adds 200 needles to usable inventory and records an exact $17.99 line cost. Each dose or preparation event deducts individual needles, not boxes.

On **Purchases → select purchase → Add supplies/pills**, choose a category and enter product name. For a bulk purchase enter all three bulk fields. The individual quantity and unit-price fields are ignored for bulk lines. The same entry method is available on **Supplies**.

Bulk package details are retained when editing a purchase line. Editing from 2 × 100 to 3 × 100 increases remaining stock by 100 without clearing existing usage. Changing the package quantity below consumed stock is rejected. Clearing all bulk fields converts the line back to legacy per-unit pricing.

Pricing uses the exact package total (in cents) for purchase subtotals and allocation of shipping, tax and discounts. Per-unit costs are derived for display; no premature rounding is applied to the bulk total.

## Deployment

1. Create a verified backup using Tracker's Backups page.
2. Replace application files, preserving `.env`, `data/`, and uploads.
3. Restart `tracker.service`. On startup, three nullable columns are added to the existing `supplies` table. Existing purchases and usage records are unchanged.
4. Hard-refresh the browser.

## Limitations

A bulk purchase line represents identical units within a single category. Mixed assortments should be entered as separate lines. A partially opened package is not tracked as a distinct physical container; stock is tracked as total usable units.
