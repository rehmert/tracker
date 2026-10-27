# Bulk vial editing

On **Vials**, check the desired rows (or use Select all visible vials). Open **Bulk edit selected vials** and choose Keep, Set, or Clear independently for each field. Only explicitly selected fields are modified. The form confirms before submitting.

Editable fields: status, lot, cap color, storage notes, notes, received date, expiration date, beyond-use date, first-puncture date, first-dose date, closed date, and whether averaged COA content is used.

The update validates all selected vials before writing, commits the batch atomically, and creates per-vial ChangeAudit entries. It does not change vial content, reconstitution volume, dose logs, purchase costs, COA links, or inventory counts. Selection applies to rows on the current filtered page only.

Installation: stop Tracker, back up /opt/tracker (including data and .env), extract the small patch into /opt/tracker, ensure files are readable by the tracker service account, restart Tracker. No database migration is needed.
