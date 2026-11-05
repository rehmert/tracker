"""Read-only authenticated storage-routing diagnostics."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..user_db389 import (
    get_user_db,
    resolve_authenticated_storage,
)
from ..request_scope393 import verified_request_scope

router = APIRouter()


@router.get("/account/storage-status")
def storage_status(
    request: Request,
    db: Session = Depends(get_user_db),
):
    """Confirm live administrator routing without reading records."""
    storage = resolve_authenticated_storage(request)

    table_count = db.execute(text("""
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type='table'
          AND name NOT LIKE 'sqlite_%'
    """)).scalar_one()

    return {
        "user_id": 1,
        "storage_mode": storage.mode,
        "database": "legacy-admin/tracker.db",
        "database_available": True,
        "application_table_count": table_count,
        "additional_users_enabled": False,
        "per_user_routing_active_globally": False,
        "records_migrated": False,
    }



@router.get("/account/isolation-status")
def isolation_status(request: Request):
    """Safe account isolation metadata; no filesystem paths."""
    scope = verified_request_scope(request)

    return {
        "authenticated_user_id": scope.user_id,
        "authentication_mode": scope.authentication_mode,
        "storage_mode": scope.storage.mode,
        "database_scope": "legacy-administrator",
        "user_specific_databases_enabled": False,
        "additional_accounts_enabled": False,
        "all_application_routes_migrated": False,
        "attachments_fully_isolated": False,
        "backups_fully_isolated": False,
        "records_migrated": False,
    }
