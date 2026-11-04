"""SQLite writer gate: lock before reading the scenario revision."""
from fastapi import HTTPException

def begin(db):
    if db.bind.dialect.name != 'sqlite':
        raise HTTPException(501, 'SQLite writer gate required')
    # Acquire the writer reservation before checking the revision.
    db.connection().exec_driver_sql('BEGIN IMMEDIATE')
