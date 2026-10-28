"""Import and normalize vendor price sheets; never infer clinical equivalence."""
import csv
import io
import re
from decimal import Decimal, InvalidOperation

HEADERS = {'item': ('item','product','compound','description','name','peptide'), 'price': ('price','cost','usd','amount','total','unit price'), 'quantity': ('quantity','qty','vials','count','pack size','units'), 'strength': ('strength','content','size','dose','mg/vial'), 'package': ('package','pack','format','type')}

def number(value):
    s = re.sub(r'[$,\s]', '', str(value or ''))
    try:
        d = Decimal(s)
        return d if d.is_finite() and d >= 0 else None
    except InvalidOperation:
        return None

def count_from_text(text):
    t = str(text or '').lower()
    m = re.search(r'(?<!\d)(\d+)\s*(?:vials?|pcs|pieces|units?|x\s*vials?)\b', t)
    if m: return int(m.group(1))
    m = re.search(r'\b(?:kit|box|pack)\s*(?:of\s*)?(\d+)\b', t)
    if m: return int(m.group(1))
    if 'half kit' in t or 'half-kit' in t: return 5
    if re.search(r'\bkit\b', t): return 10
    return 1

def parse_lines(text):
    """Accept CSV, TSV or simple OCR rows with item and price at the end."""
    text = text.lstrip('\ufeff')
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines: return []
    delimiter = '\t' if sum('\t' in x for x in lines[:5]) > sum(',' in x for x in lines[:5]) else ','
    rows = list(csv.reader(io.StringIO('\n'.join(lines)), delimiter=delimiter))
    header = [x.strip().lower() for x in rows[0]]
    mapping = {}
    for key, aliases in HEADERS.items():
        for i, name in enumerate(header):
            if name in aliases or any(name.startswith(a + ' ') for a in aliases):
                mapping[key] = i; break
    output = []
    if 'item' in mapping and 'price' in mapping:
        for row in rows[1:]:
            def col(key):
                i = mapping.get(key)
                return row[i].strip() if i is not None and i < len(row) else ''
            item = col('item'); price = number(col('price'))
            if not item or price is None: continue
            qty = number(col('quantity'))
            package = col('package')
            quantity = int(qty) if qty and qty == int(qty) else count_from_text(item + ' ' + package)
            if quantity < 1 or quantity > 100000: continue
            output.append((item[:200], col('strength')[:80], package[:80], quantity, price))
    else:
        for row in rows:
            if len(row) >= 2 and number(row[-1]) is not None:
                item = ' '.join(x.strip() for x in row[:-1]).strip()
                if item: output.append((item[:200], '', '', count_from_text(item), number(row[-1])))
            elif len(row) == 1:
                m = re.match(r'^(.+?)\s+\$?([\d,]+(?:\.\d{1,4})?)\s*$', row[0].strip())
                if m: output.append((m.group(1)[:200], '', '', count_from_text(m.group(1)), number(m.group(2))))
    return output[:500]

def normalize_item(text):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', str(text).lower())).strip()
