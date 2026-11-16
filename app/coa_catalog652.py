"""Release 652: editable COA test-type catalog, compatible with Release 651.

Catalog IDs are stable. Never mutate an attachment's stored test classification
when an operator renames, regroups, or deactivates its catalog entry.
All older standalone and ~651~ classifications remain readable.
"""
from __future__ import annotations

import json
from collections import OrderedDict

from sqlalchemy import select

from .coa_test_types646 import COA_TEST_TYPE_GROUPS
from .coa_multitypes651 import (
    CODEBOOK, CODE_IDS, PREFIX as OLD_PREFIX,
    decode as decode651, from_selection as select651,
)
from .models import CoaTestType652

PREFIX = "~652~"
CUSTOM_ID_PREFIX = "@652:"
MAX_SAVED_BYTES = 120


def seed_catalog652(engine):
    """Idempotent additive seed at startup, never on GET/read-only routes."""
    with engine.begin() as conn:
        for group, options in COA_TEST_TYPE_GROUPS:
            for position, (code, title) in enumerate(options):
                conn.exec_driver_sql(
                    """INSERT OR IGNORE INTO coa_test_type_catalog652
                    (builtin_code, label, group_name, active, position)
                    VALUES (?, ?, ?, 1, ?)""",
                    (code, title, group, position),
                )


def catalog652(db):
    return list(db.scalars(select(CoaTestType652).order_by(CoaTestType652.id)))


def key652(item):
    return item.builtin_code or f"{CUSTOM_ID_PREFIX}{item.id}"


def display652(item):
    """Keep historical short summaries until their built-in label is edited."""
    for _group, options in COA_TEST_TYPE_GROUPS:
        for code, title in options:
            if item.builtin_code == code and item.label == title:
                return code
    return item.label


def groups652(items):
    order = {group: i for i, (group, _) in enumerate(COA_TEST_TYPE_GROUPS)}
    grouped = OrderedDict()
    for item in sorted(items, key=lambda row: (
        order.get(row.group_name, 99), row.group_name.casefold(),
        row.position, row.id,
    )):
        group = item.group_name
        grouped.setdefault(group, [])
        grouped[group].append((
            key652(item), item.label + (" (inactive)" if not item.active else ""),
            bool(item.active), display652(item),
        ))
    return tuple((group, tuple(options)) for group, options in grouped.items())


def selections652(stored):
    """Return stable picker values; preserve unrecognized historic literal data."""
    if not stored or not stored.startswith(PREFIX):
        return decode651(stored)
    try:
        tokens = json.loads(stored[len(PREFIX):])
        if not isinstance(tokens, list) or not 1 <= len(tokens) <= 25:
            raise ValueError("Bad length")
        seen = set()
        result = []
        custom = 0
        for token in tokens:
            if type(token) is int and 0 <= token < len(CODEBOOK):
                label = CODEBOOK[token]
            elif type(token) is int and token < 0:
                label = f"{CUSTOM_ID_PREFIX}{-token}"
            elif (isinstance(token, str) and 0 < len(token) <= 120
                  and token not in CODE_IDS
                  and not token.startswith((CUSTOM_ID_PREFIX, PREFIX, OLD_PREFIX))):
                label = token
                custom += 1
            else:
                raise ValueError("Invalid selection token")
            if label in seen:
                raise ValueError("Duplicate token")
            seen.add(label)
            result.append(label)
        if custom > 1:
            raise ValueError("Too many ad hoc labels")
        return result
    except (ValueError, TypeError, json.JSONDecodeError):
        return [stored]


def test_info652(stored, items):
    selected = selections652(stored)
    lookup = {key652(item): display652(item) for item in items}
    return {
        "test_selected": selected,
        "test_types": [lookup.get(value, value) for value in selected],
        "custom_type": next((
            value for value in selected
            if value not in CODE_IDS and not value.startswith(CUSTOM_ID_PREFIX)
        ), ""),
    }


def from_selection652(checked, custom, items, previous=""):
    """Validate a whole selection before changing any attachment.

    Disabled categories are available only to preserve selections already on
    the document. Unknown/forged catalog IDs are never accepted.
    """
    if not isinstance(checked, list) or len(checked) > 26:
        raise ValueError("Too many test selections.")
    previous_keys = set(selections652(previous))
    active_keys = {key652(item) for item in items if item.active}
    all_keys = {key652(item) for item in items}
    selected = [v for v in checked if v]
    if len(selected) != len(set(selected)):
        raise ValueError("Duplicate test selection.")
    for value in selected:
        if (value not in all_keys or
                (value not in active_keys and value not in previous_keys)):
            raise ValueError("Choose only available COA test types.")
    custom = custom.strip() if isinstance(custom, str) else ""
    if custom and (len(custom) > 120 or custom.startswith(
            (CUSTOM_ID_PREFIX, PREFIX, OLD_PREFIX))):
        raise ValueError("Invalid custom COA test type.")
    if not any(value.startswith(CUSTOM_ID_PREFIX) for value in selected):
        return select651(selected, custom)
    builtin = sorted((v for v in selected if v in CODE_IDS),
                     key=CODE_IDS.__getitem__)
    user_ids = sorted(
        (int(v[len(CUSTOM_ID_PREFIX):])
         for v in selected if v.startswith(CUSTOM_ID_PREFIX))
    )
    tokens = [CODE_IDS[v] for v in builtin] + [-i for i in user_ids]
    if custom:
        if custom in selected:
            raise ValueError("Duplicate test type.")
        tokens.append(custom)
    if len(tokens) > 25:
        raise ValueError("Too many test types for a document.")
    encoded = PREFIX + json.dumps(tokens, ensure_ascii=True, separators=(",", ":"))
    if len(encoded) > MAX_SAVED_BYTES:
        raise ValueError("Combined COA tests exceed the existing 120-character storage limit.")
    return encoded
