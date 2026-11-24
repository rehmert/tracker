"""Conservative 5-minute sync; no network unless configured and connected."""
import asyncio
import logging
from .google_tasks_client769 import configured769, GoogleTasksError769
from .google_tasks_sync769 import sync_once769

logger = logging.getLogger(__name__)


async def loop769():
    while True:
        await asyncio.sleep(300)
        if not configured769():
            continue
        try:
            await asyncio.to_thread(sync_once769)
        except (GoogleTasksError769, OSError, ValueError):
            logger.warning("Google Tasks 769 sync deferred; review private status page")
