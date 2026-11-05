"""Request-authorized food dashboard engine dependency.

Reuse the existing Release 392 authorization without
introducing a circular import into app.routers.food.

Secondary-user engines remain disabled.
"""

from fastapi import Request


def get_food_read_engine406(request: Request):
    from .food_engine392 import get_food_engine392

    return get_food_engine392(request)
