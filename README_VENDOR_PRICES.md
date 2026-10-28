# Vendor price comparison

The `/vendor-prices` route imports CSV, TSV, TXT, XLSX, or OCR-extracted PNG/JPG/WebP price sheets. Every import requires an editable review step before database changes. Saved offers are grouped by normalized product name + strength, and compared by price per vial. Prices do not include shipping, taxes, or discounts; offers with different naming or strength are not automatically matched. OCR is best-effort and may miss rows.

Install updated Python dependencies: `pip install -r requirements.txt` in Tracker's virtual environment. For image OCR also install `Pillow pytesseract` into that environment and install the OS `tesseract` executable (e.g. `dnf install tesseract` or `apt install tesseract-ocr`). OCR is optional: CSV/XLSX imports work without it.

New tables `vendor_price_sheets` and `vendor_price_entries` are created by existing SQLAlchemy `create_all` at startup. Back up the database before updating. Existing inventory and purchase records are untouched. Images and original uploaded files are not retained; only reviewed rows are stored.
