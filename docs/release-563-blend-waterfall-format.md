# Release 563 — Recordable blend previews, waterfall, and readable numbers

## One workflow for creating blends
- Enter destination label, choose at least two source vials, and supply a per-draw target for each compound. Transfer fields are optional (advanced mode).
- **Preview blend** uses the read-only calculation for dry sources or blank measured transfers; with existing liquid/measured sources it uses the conventional preview.
- A successful preview now enables **Record confirmed blend** for either mode. Before submission the browser checks that form inputs are unchanged and asks the operator to confirm that the shown physical quantities were actually prepared/transferred.
- The new server endpoint `POST /blends/record-plan` revalidates the entire calculation under an inventory write lock, requires a unique submission token and explicit confirmation, records actual source reconstitutions for dry sources, writes Blend / BlendComponent records and audit entries, and deducts source content exactly once. Failure rolls back the transaction.
- The existing measured-transfer `POST /blends` path remains supported.

## Sequential waterfall (2–6 dry vials)
- On the Blends page, choose 2–6 distinct, dry, unused source vials **of the same compound** in their actual transfer order, initial BAC volume, capacity, a target amount/unit, and an output label.
- `POST /blends/waterfall/preview` does **not** change the database.
- `POST /blends/waterfall/record` requires confirmation and recomputes/validates under the inventory lock, then records a single Blend representing the finished mixture and consumes each original source record once.
- The last source vial is identified as the actual physical container in the Blend notes. The existing blended-vial dose workflow can track subsequent consumption.
- The model assumes additive nominal contents, full transfer with zero physical loss, no displacement, and no compatibility or sterility assurance. **This is an inventory record, not procedural advice.**
- This workflow does not automatically debit a BAC-water supply item; if separate supply accounting is required, record that explicitly using the existing supply workflow. It does not change any schema.

## Numbers
- Read-only numeric display: maximum three digits following the decimal point, no scientific notation; nonzero magnitudes smaller than the representable threshold display as `<0.001` or `>-0.001`.
- Central number filters and specific blend, labs, inventory, dosing, reconstitution, and PK formatters updated.
- A presentation-only numeric text observer catches older user-visible calculation text on pages and dynamically inserted UI. It does not rewrite inputs, code snippets, URLs, stored values, or APIs.
- Full precision **continues** in calculations and persisted data to avoid corrupting inventory balances or historical results. Existing numeric **edit inputs** retain their exact values; rounding an editable value could silently change it on Save.

## Release checks
- New tests cover record-plan success, rejection without confirmation, idempotency, partial inventory balances, waterfall recording and invalid sources, and display formatting.
- Follow the pinned DEV release runner for isolated browser qualification, full backend suite, backup/restore verification, and runtime smoke. Do not promote to PROD until all gates pass and an exact-commit signed DEV approval is produced.
