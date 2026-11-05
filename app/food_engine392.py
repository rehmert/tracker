"""Release 392: request-authorized food engine selection.

The authenticated administrator still uses the original engine.
Additional user engines remain disabled.

Standalone legacy tests may inject an isolated engine through
app.routers.food.engine while session authentication is off.
"""

from fastapi import HTTPException, Request

from . import session_auth385
from .db import engine as administrator_engine
from .food_storage_guard391 import require_food_storage391
from .routers import food


def get_food_engine392(request: Request):
    """Resolve an engine only after checking request authorization."""

    # The direct call ensures that even an isolated endpoint
    # using this dependency cannot bypass the food guard.
    require_food_storage391(request)

    selected = food.engine

    if session_auth385.enabled():
        # No future-user engine can be substituted here.
        if selected is not administrator_engine:
            raise HTTPException(
                503,
                "Food database engine configuration mismatch",
            )

    return selected
