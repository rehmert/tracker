# Purchase line-item editing

Purchase detail pages now support editing/deleting purchased supplies and pills, and link to existing vial editing with a purchase-level delete action.

- Supply and pill edits update name, type (only if unused), compound, quantity, price and notes.
- Changes to purchased quantity adjust remaining stock by the difference; they do not reset consumption.
- Deletion is refused for supplies/pills with usage or adjusted stock and for vials with doses/waste or associated reconstitution supply usage.
- Editing a vial is done via its existing detail page; the purchase view links there.
- Landed costs are recalculated from current line items and purchase shipping/tax/discount.
- No schema migration is needed.

Deploy over your current application while preserving `.env`, database, and uploaded assets. Back up your database first. Restart the service and hard-refresh the browser.
