"""Local, bounded PDF lab extraction. Never infer exact values from inequalities."""
import re
import shutil
import subprocess
import tempfile
import csv
import io
import time
import math
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation

MAX_BYTES = 15 * 1024 * 1024
MAX_TEXT = 500_000
MAX_PAGES = 30
MAX_OCR_PAGES = 8
NUM = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"
RANGE = re.compile(r"^(" + NUM + r")\s*[-–—]\s*(" + NUM + r")$")
UNIT = re.compile(r"^(?:[a-zA-Zµμ%][a-zA-Z0-9µμ%/^.*·()_-]{0,29}|10\^[0-9]+/[a-zA-Zµμ]+)$")
DATE = re.compile(r"(?i)(?:date\s+(?:collected|drawn)|collection date|collected(?:\s+on)?|drawn(?:\s+on)?|specimen collected)\s*[: ]+\s*(\d{1,4}[-/]\d{1,2}[-/]\d{2,4})")
QUAL = re.compile(r"(?i)^(?:[<>≤≥]|negative\b|positive\b|nonreactive\b|reactive\b|pending\b|not detected\b|detected\b)")

def _command(args, timeout):
    try:
        outcome = subprocess.run(args, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("Local document processing failed or timed out.") from None
    if outcome.returncode:
        raise ValueError("Local document processing could not read this PDF.")

def _ocr(src, folder, count):
    render, ocr = shutil.which("pdftoppm"), shutil.which("tesseract")
    if not render or not ocr:
        raise ValueError("Scanned PDF requires local Poppler rendering and Tesseract OCR.")
    if count > MAX_OCR_PAGES:
        raise ValueError("Split scanned PDFs into at most eight pages.")
    deadline = time.monotonic() + 75
    def run(args):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("Scanned PDF processing timed out.")
        _command(args, min(30, remaining))
    pages = []
    for page in range(1, count + 1):
        stem = Path(folder) / "scan"
        image = stem.with_suffix(".png")
        output = stem.with_suffix(".tsv")
        run([render, "-f", str(page), "-l", str(page), "-singlefile", "-scale-to", "2400", "-png", str(src), str(stem)])
        run([ocr, str(image), str(stem), "--psm", "6", "tsv"])
        if not output.exists() or output.stat().st_size > MAX_TEXT * 4:
            raise ValueError("OCR output exceeds review limits.")
        # Reconstruct text lines using actual horizontal word gaps, not a
        # fixed number of spaces between every word.
        lines = {}
        for word in csv.DictReader(io.StringIO(output.read_text(encoding="utf-8")), delimiter="\t"):
            if word["level"] != "5" or not word["text"].strip():
                continue
            key = (word["block_num"], word["par_num"], word["line_num"])
            lines.setdefault(key, []).append((int(word["left"]), int(word["width"]),
                                              int(word["height"]), word["text"]))
        page_lines = []
        for words in lines.values():
            last = None
            line = ""
            for left, width, height, text in sorted(words):
                if last is not None:
                    line += "  " if left - last > max(18, height) else " "
                line += text
                last = left + width
            page_lines.append(line)
        pages.append("\n".join(page_lines))
        image.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
    return "\f".join(pages)

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
        pages = text.split("\f")
        if pages and pages[-1] == "":
            pages.pop()
        if len(pages) > MAX_PAGES:
            raise ValueError("PDF exceeds the 30-page review limit.")
        if any(not page.strip() for page in pages):
            text = _ocr(src, folder, len(pages) or 1)
            text = "OCR REVIEW REQUIRED\n" + text
    if not text.replace("OCR REVIEW REQUIRED", "").strip():
        raise ValueError("No readable text found in PDF.")
    if len(text) > MAX_TEXT:
        raise ValueError("PDF exceeds extraction limits.")
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
    if text.startswith("OCR REVIEW REQUIRED"):
        warnings.append("OCR was used; carefully verify every digit and symbol against the PDF.")
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
                active = not bool(re.search(r"\b(?:previous|historical|prior)\b", lower))
                if not active:
                    warnings.append(f"Page {page_no}: historical-result columns require manual review.")
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
            value = re.fullmatch("(" + NUM + r")(?:\s+(?:H|L|High|Low))?", raw, re.I)
            qualified = bool(re.fullmatch(r"[<>≤≥]\s*"+NUM, raw))
            qualitative = raw.casefold() in {"negative","positive","nonreactive","non-reactive","reactive","pending","not detected","detected","indeterminate"}
            if not value and not qualified and not qualitative:
                if re.search(r"\d", raw):
                    warnings.append(f"Page {page_no}: check unparsed row — {line[:240]}")
                continue
            parts = [x for x in cols[2:] if x.lower() not in {"h", "l", "high", "low", "normal", "abnormal"}]
            single_ranges = [x for x in parts if re.fullmatch(r"[<>≤≥]\s*"+NUM, x)]
            parts = [x for x in parts if x not in single_ranges]
            ranges = [RANGE.fullmatch(x) for x in parts]
            ranges = [x for x in ranges if x]
            units = [x for x in parts if UNIT.fullmatch(x) and not RANGE.fullmatch(x)]
            if (len(units) > 1 or (not units and not qualitative) or len(ranges)+len(single_ranges)>1
                    or len(parts) != len(units) + len(ranges)):
                warnings.append(f"Page {page_no}: ambiguous units/range — {line[:240]}")
                continue
            lo, hi = ranges[0].groups() if ranges else ("", "")
            try:
                if lo and Decimal(lo) > Decimal(hi):
                    raise InvalidOperation
            except InvalidOperation:
                warnings.append(f"Page {page_no}: invalid reference range — {line[:240]}")
                continue
            flags = re.findall(r"(?i)(?:^|\s)(H|L|High|Low|Abnormal)(?=\s|$)", " ".join(cols[1:]))
            rows.append(dict(analyte=name, value=value.group(1) if value else raw, unit=units[0] if units else "",
                             ref_low=lo, ref_high=hi, printed_range=single_ranges[0] if single_ranges else "",
                             flag=flags[0] if flags else "", source=line[:240], page=page_no))
    return dict(lab_name=lab, drawn_on=next(iter(dates)) if len(dates)==1 else "",
                rows=rows, warnings=warnings)

def validate_review(rows):
    """Validate reviewed data independent of browser controls and source parser."""
    from . import labs
    if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
        raise ValueError("Review between 1 and 500 result rows.")
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid reviewed result.")
        clean = {}
        for field, limit in (("analyte",120),("value",80),("unit",30),
                             ("ref_low",40),("ref_high",40),("printed_range",80),("flag",30)):
            value = row.get(field, "")
            if not isinstance(value, str) or len(value.strip()) > limit:
                raise ValueError("Invalid reviewed result field.")
            clean[field] = value.strip()
        name, raw, unit = (clean[k] for k in ("analyte","value","unit"))
        if not name or not raw:
            raise ValueError("Every reviewed row needs an analyte and result.")
        # Use existing canonical names only for known exact aliases.
        key = labs.analyte_key(name)
        clean["analyte"] = next((n for n in labs.COMMON_ANALYTES if labs.analyte_key(n)==key), name)
        exact = re.fullmatch(NUM, raw)
        qualified = re.fullmatch(r"[<>≤≥]\s*" + NUM, raw)
        qualitative = raw.casefold() in {"negative","positive","nonreactive","non-reactive",
                  "reactive","pending","not detected","detected","indeterminate","equivocal"}
        if not (exact or qualified or qualitative):
            raise ValueError("Unrecognized result format: review the measurement.")
        if not qualitative and not unit:
            raise ValueError("Numeric and qualified results require the printed unit.")
        for key in ("ref_low", "ref_high"):
            bound = clean[key]
            if bound and (not re.fullmatch(NUM, bound) or not math.isfinite(float(bound))):
                raise ValueError("Reference limits must be finite numbers.")
        lo, hi = clean["ref_low"], clean["ref_high"]
        if lo and hi and float(lo) > float(hi):
            raise ValueError("Reference low exceeds high.")
        if exact and not math.isfinite(float(raw)):
            raise ValueError("Result must be finite.")
        if clean["printed_range"] and (lo or hi):
            raise ValueError("Use either printed range text or numeric reference limits.")
        if not clean["printed_range"] and (lo or hi) and not (lo and hi):
            clean["printed_range"] = ("≥" + lo) if lo else ("≤" + hi)
            clean["ref_low"] = clean["ref_high"] = ""
        clean["exact"] = bool(exact)
        result.append(clean)
    return result
