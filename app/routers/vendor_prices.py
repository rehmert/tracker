"""Vendor sheet comparison, including a reviewable import pipeline."""
import csv
import io
import re
from decimal import Decimal
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import VendorPriceSheet, VendorPriceEntry
from ..templating import render
from .. import services
from ..vendor_prices import parse_lines, number, normalize_item

router = APIRouter()
MAX_UPLOAD = 8 * 1024 * 1024

def rows_text(rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter='\t', lineterminator='\n')
    writer.writerow(('Item', 'Strength', 'Package', 'Vials', 'Total USD'))
    for item, strength, package, qty, price in rows:
        writer.writerow((item, strength, package, qty, str(price)))
    return buffer.getvalue()

def parse_review(text):
    lines = list(csv.reader(io.StringIO(text), delimiter='\t'))
    result = []
    for idx, row in enumerate(lines):
        if not row or not any(x.strip() for x in row): continue
        if idx == 0 and row[0].strip().lower() == 'item': continue
        if len(row) != 5: raise ValueError(f'Row {idx+1}: expected five tab-separated columns.')
        item, strength, package, qty, price = [x.strip() for x in row]
        if not item: raise ValueError(f'Row {idx+1}: item is required.')
        try: count = int(qty)
        except ValueError: raise ValueError(f'Row {idx+1}: vial count must be an integer.')
        value = number(price)
        if not 1 <= count <= 100000 or value is None: raise ValueError(f'Row {idx+1}: invalid count or price.')
        result.append((item[:200], strength[:80], package[:80], count, value))
    if len(result) > 500: raise ValueError('Maximum 500 items per sheet.')
    return result

def page(request, db, **kwargs):
    sheets = list(db.scalars(select(VendorPriceSheet).order_by(VendorPriceSheet.id.desc())))
    entries = list(db.scalars(select(VendorPriceEntry).order_by(VendorPriceEntry.item_name, VendorPriceEntry.id)))
    groups = {}
    for entry in entries:
        key = (normalize_item(entry.item_name), normalize_item(entry.strength))
        groups.setdefault(key, []).append(entry)
    comparisons = sorted(groups.values(), key=lambda group: (group[0].item_name.lower(), group[0].strength.lower()))
    return render(request, 'vendor_prices.html', sheets=sheets, comparisons=comparisons, **kwargs)

@router.get('/vendor-prices')
def index(request: Request, db: Session = Depends(get_db)):
    return page(request, db)

@router.post('/vendor-prices/preview')
async def preview(request: Request, vendor: str = Form(''), sheet_name: str = Form(''), upload: UploadFile = File(...), db: Session = Depends(get_db)):
    vendor = vendor.strip()[:160]
    if not vendor: return page(request, db, err='Vendor name is required.')
    filename = (upload.filename or '').lower()
    if not filename.endswith(('.csv', '.tsv', '.txt', '.xlsx', '.png', '.jpg', '.jpeg', '.webp')):
        return page(request, db, err='Upload CSV, TSV, XLSX, PNG, JPG or WebP.')
    data = await upload.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD: return page(request, db, err='Maximum upload size is 8 MB.')
    try:
        if filename.endswith('.xlsx'):
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            output = io.StringIO(); writer = csv.writer(output)
            for row in wb.active.iter_rows(values_only=True):
                writer.writerow(['' if v is None else str(v) for v in row])
            wb.close(); raw = output.getvalue()
        elif filename.endswith(('.png','.jpg','.jpeg','.webp')):
            from PIL import Image
            import pytesseract
            img = Image.open(io.BytesIO(data))
            img.verify()
            img = Image.open(io.BytesIO(data))
            if img.width * img.height > 20_000_000: raise ValueError('Image too large (20 megapixels maximum).')
            raw = pytesseract.image_to_string(img)
        else:
            raw = data.decode('utf-8-sig')
        parsed = parse_lines(raw)
    except ImportError:
        return page(request, db, err='Optional parser dependency missing. Install openpyxl for XLSX, or Pillow + pytesseract + Tesseract for images.')
    except Exception as exc:
        return page(request, db, err=f'Could not parse uploaded sheet: {str(exc)[:200]}')
    return page(request, db, vendor=vendor, sheet_name=sheet_name[:160] or upload.filename, review_text=rows_text(parsed), preview_count=len(parsed), raw_text=raw[:8000])

@router.post('/vendor-prices/save')
def save(request: Request, vendor: str = Form(...), sheet_name: str = Form(''), review_text: str = Form(...), db: Session = Depends(get_db)):
    vendor = vendor.strip()[:160]
    if not vendor: return page(request, db, err='Vendor name is required.', review_text=review_text)
    try: rows = parse_review(review_text)
    except ValueError as exc: return page(request, db, err=str(exc), vendor=vendor, sheet_name=sheet_name, review_text=review_text)
    if not rows: return page(request, db, err='No valid rows to save.', vendor=vendor, sheet_name=sheet_name, review_text=review_text)
    sheet = VendorPriceSheet(vendor=vendor, name=sheet_name.strip()[:160])
    db.add(sheet); db.flush()
    for item, strength, package, qty, price in rows:
        db.add(VendorPriceEntry(sheet_id=sheet.id, item_name=item, strength=strength, package=package, vial_count=qty, total_price_cents=int((price * 100).quantize(Decimal('1')))))
    db.commit()
    return services.flash_redirect('/vendor-prices', msg=f'Saved {len(rows)} offers for {vendor}.')

@router.post('/vendor-prices/{sheet_id}/delete')
def delete(sheet_id: int, db: Session = Depends(get_db)):
    sheet = db.get(VendorPriceSheet, sheet_id)
    if sheet:
        db.delete(sheet); db.commit()
    return services.flash_redirect('/vendor-prices', msg='Price sheet deleted.')
