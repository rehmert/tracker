"""Local, bounded PDF lab extraction. Never infer exact values from inequalities."""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation

MAX_BYTES = 15 * 1024 * 1024
MAX_TEXT = 500_000
MAX_PAGES = 30
NUM = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"
RANGE = re.compile(r"^(" + NUM + r")\s*[-–—]\s*(" + NUM + r")$")
UNIT = re.compile(r"^(?:[a-zA-Zµμ%][a-zA-Z0-9µμ%/^.*·()_-]{0,29}|10\^[0-9]+/[a-zA-Zµμ]+)$")
DATE = re.compile(r"(?i)(?:date\s+(?:collected|drawn)|collection date|collected(?:\s+on)?|drawn(?:\s+on)?|specimen collected)\s*[: ]+\s*(\d{1,4}[-/]\d{1,2}[-/]\d{2,4})")
QUAL = re.compile(r"(?i)^(?:[<>≤≥]|negative\b|positive\b|nonreactive\b|reactive\b|pending\b|not detected\b|detected\b)")

def extract_text(data):
    if not data or len(data) > MAX_BYTES or not data.startswith(b"%PDF-"):
        raise ValueError("Select a valid PDF no larger than 15 MB.")
    exe = shutil.which("pdftotext")
    if not exe:
        raise ValueError("Local PDF extractor unavailable: install Poppler pdftotext on the server.")
    with tempfile.TemporaryDirectory(prefix="tracker-lab-pdf-") as folder:
        src = Path(folder) / "input.pdf"
        dst = Path(folder) / "output.txt"
        src.write_bytes(data)
        try:
            result = subprocess.run([exe, "-f", "1", "-l", str(MAX_PAGES + 1),
                                     "-layout", "-enc", "UTF-8", str(src), str(dst)],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError("PDF extraction failed or timed out.") from None
        if result.returncode or not dst.exists() or dst.stat().st_size > MAX_TEXT:
            raise ValueError("PDF could not be read or exceeds extraction limits.")
        text = dst.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        raise ValueError("No embedded text found. This scanned PDF needs OCR before importing.")
    if len(text.rstrip("\f").split("\f")) > MAX_PAGES:
        raise ValueError("PDF exceeds the 30-page review limit.")
    return text

def parse_text(text):
    """Conservative layout parser. Ambiguous rows are shown, never silently saved."""
    lab = "Labcorp" if re.search(r"\blabcorp\b", text, re.I) else (
        "Quest Diagnostics" if re.search(r"\bquest diagnostics\b", text, re.I) else "")
    dates = set()
    for match in DATE.finditer(text):
        raw = match.group(1)
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y", "%Y/%m/%d"):
            try:
                dates.add(datetime.strptime(raw, fmt).date().isoformat())
                break
            except ValueError:
                pass
    rows, warnings = [], []
    if len(dates) != 1:
        warnings.append("Confirm collection date against the original report; no single date was identified.")
    # Only parse explicit column boundaries; do not guess from prose or historical columns.
    active = False
    for page_no, page in enumerate(text.split("\f"), 1):
        active = False
        for line in page.splitlines():
            line = line.strip()
            if not line:
                continue
            cols = re.split(r"\s{2,}|\t+", line)
            lower = line.lower()
            if ("result" in lower and ("test" in lower or "analyte" in lower)
                    and ("unit" in lower or "reference" in lower)):
                active = True
                continue
            if not active or len(cols) < 2:
                continue
            if len(rows) + len(warnings) >= 500:
                raise ValueError("Too many candidate rows; split the report into smaller PDFs.")
            name, raw = cols[0], cols[1]
            if not re.search(r"[A-Za-z]", name) or len(name) > 120:
                continue
            if re.search(r"(?i)\b(?:previous|historical|prior)\b", lower):
                warnings.append(f"Page {page_no}: historical or ambiguous row — {line[:240]}")
                continue
            if QUAL.match(raw):
                warnings.append(f"Page {page_no}: qualified/qualitative result excluded from numeric trends — {line[:240]}")
                continue
            value = re.fullmatch("(" + NUM + r")(?:\s+(?:H|L|High|Low))?", raw, re.I)
            if not value:
                if re.search(r"\d", raw):
                    warnings.append(f"Page {page_no}: check unparsed row — {line[:240]}")
                continue
            parts = [x for x in cols[2:] if x.lower() not in {"h", "l", "high", "low", "normal", "abnormal"}]
            ranges = [RANGE.fullmatch(x) for x in parts]
            ranges = [x for x in ranges if x]
            units = [x for x in parts if UNIT.fullmatch(x) and not RANGE.fullmatch(x)]
            if len(units) != 1 or len(ranges) > 1 or len(parts) != len(units) + len(ranges):
                warnings.append(f"Page {page_no}: ambiguous units/range — {line[:240]}")
                continue
            lo, hi = ranges[0].groups() if ranges else ("", "")
            try:
                if lo and Decimal(lo) > Decimal(hi):
                    raise InvalidOperation
            except InvalidOperation:
                warnings.append(f"Page {page_no}: invalid reference range — {line[:240]}")
                continue
            rows.append(dict(analyte=name, value=value.group(1), unit=units[0],
                             ref_low=lo, ref_high=hi, source=line[:240], page=page_no))
    return dict(lab_name=lab, drawn_on=next(iter(dates)) if len(dates)==1 else "",
                rows=rows, warnings=warnings)
