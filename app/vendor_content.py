"""Structured per-vial vendor content and conservative legacy conversion."""
import re
from decimal import Decimal, InvalidOperation

CONTENT_RE = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*(mg|iu)\s*(?:/\s*vial|per\s+vial|\(\s*per\s+vial\s*\)|\(\s*each\s*\))?\s*$', re.I)

def parse_legacy_content(text):
    match = CONTENT_RE.fullmatch(text or '')
    if not match:
        return None, None
    amount = Decimal(match.group(1))
    if not amount.is_finite() or amount <= 0:
        return None, None
    return amount, 'IU' if match.group(2).lower() == 'iu' else 'mg'

def validate_content(amount_text, unit):
    try:
        amount = Decimal(str(amount_text).strip())
    except (InvalidOperation, ValueError):
        raise ValueError('Content per vial must be a positive number.')
    if not amount.is_finite() or amount <= 0 or amount > Decimal('100000000'):
        raise ValueError('Content per vial must be between 0 and 100,000,000.')
    if unit not in ('mg', 'IU'):
        raise ValueError('Content unit must be mg or IU.')
    return amount, unit

def label(amount, unit):
    return f'{format(Decimal(str(amount)).normalize(), "f")} {unit}/vial'
