"""Durable replay detection; call after acquiring BEGIN IMMEDIATE."""
import hashlib
import json
import uuid
from sqlalchemy.orm import Session
from .models import InventorySubmission

def new_token():
    return str(uuid.uuid4())

def check(db: Session, token: str, operation: str, payload) -> tuple[str, str]:
    try:
        canonical = str(uuid.UUID(str(token)))
    except (ValueError, TypeError, AttributeError):
        return "invalid", ""
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()
    prior = db.get(InventorySubmission, canonical)
    if prior is None:
        return "new", digest
    if prior.operation == operation and prior.payload_hash == digest:
        return "replay", digest
    return "conflict", digest

def record(db: Session, token: str, operation: str, digest: str):
    db.add(InventorySubmission(token=str(uuid.UUID(token)), operation=operation, payload_hash=digest))
