"""Release 651: several independently identified tests per uploaded COA file.

Use the existing coas_attachments.test_type column without migrating any
historical database or upload. Legacy single labels are stored unchanged.
Multi-label selections are compact, stable-index JSON with a version tag.
The codebook below is append-only: NEVER reorder or reuse its indices.
"""
from __future__ import annotations

import json

from .coa_test_types646 import COA_TEST_TYPE_VALUES

PREFIX = "~651~"
CODEBOOK = (
    "Purity", "Identity", "Purity & identity", "Net peptide content",
    "Potency / content", "Concentration", "Conformity / variance",
    "Endotoxin", "Sterility", "Microbial screening", "Bioburden",
    "Heavy metals", "Fentanyl", "Residual solvents", "TFA", "pH",
    "CHNS", "LC-MS", "GC-MS", "HGH dimer", "BA/BB",
    "Counterions", "Stability", "Full QC panel",
)
assert len(CODEBOOK) == len(set(CODEBOOK))
assert set(CODEBOOK) == COA_TEST_TYPE_VALUES
CODE_IDS = {name: index for index, name in enumerate(CODEBOOK)}


def decode(stored: str | None) -> list[str]:
    """Decode one attachment's labels, preserving historic unknown strings."""
    if not stored:
        return []
    if not stored.startswith(PREFIX):
        return [stored]
    try:
        tokens = json.loads(stored[len(PREFIX):])
        if not isinstance(tokens, list) or len(tokens) < 2 or len(tokens) > 25:
            raise ValueError("Invalid length")
        labels: list[str] = []
        for token in tokens:
            if type(token) is int and 0 <= token < len(CODEBOOK):
                label = CODEBOOK[token]
            elif isinstance(token, str) and token and len(token) <= 120 and token not in CODE_IDS:
                label = token
            else:
                raise ValueError("Invalid token")
            if label in labels:
                raise ValueError("Repeated label")
            labels.append(label)
        if sum(label not in CODE_IDS for label in labels) > 1:
            raise ValueError("Too many custom types")
        return labels
    except (ValueError, TypeError, json.JSONDecodeError):
        # A legacy custom label could coincidentally begin with the marker;
        # always render its original value instead of losing it.
        return [stored]


def encode(labels: list[str]) -> str:
    """Validate, canonicalize, encode all labels within existing 120-char field."""
    if not isinstance(labels, list):
        raise ValueError("Select valid test types.")
    seen: set[str] = set()
    custom: str | None = None
    for item in labels:
        if not isinstance(item, str):
            raise ValueError("Invalid test type.")
        name = item.strip()
        if not name:
            continue
        if len(name) > 120 or name.startswith(PREFIX):
            raise ValueError("Test type must be 1-120 characters without reserved encoding.")
        if name in seen:
            raise ValueError("Duplicate test type.")
        seen.add(name)
        if name not in CODE_IDS:
            if custom is not None:
                raise ValueError("Select at most one custom test type.")
            custom = name
    if not seen:
        return ""
    ordered = [name for name in CODEBOOK if name in seen]
    if custom:
        ordered.append(custom)
    if len(ordered) == 1:
        return ordered[0]
    tokens: list[int | str] = [CODE_IDS[x] if x in CODE_IDS else x for x in ordered]
    encoded = PREFIX + json.dumps(tokens, ensure_ascii=True, separators=(",", ":"))
    if len(encoded) > 120:
        raise ValueError("Too many combined test types for one document (120-character storage limit).")
    return encoded


def from_selection(checked: list[str], custom: str) -> str:
    """New checkbox editor: allow catalog types and one optional custom."""
    if not isinstance(checked, list) or len(checked) > len(CODEBOOK) + 1:
        raise ValueError("Too many test type selections.")
    selected = [name for name in checked if name]
    if any(name not in CODE_IDS for name in selected):
        raise ValueError("Select only the listed test types.")
    if custom and custom.strip():
        selected.append(custom.strip())
    return encode(selected)
