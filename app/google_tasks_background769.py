"""One-minute completion checks; full Google Tasks reconciliation every 5 minutes.

No live network is attempted unless the existing PROD-only OAuth settings
are configured. Both passes use the same nonblocking cross-worker lock.
"""
import asyncio
import logging

from .google_tasks_client769 import configured769, GoogleTasksError769
from .google_tasks_sync769 import sync_once769, sync_completions_once780

logger = logging.getLogger(__name__)

COMPLETION_POLL_SECONDS_780 = 60
FULL_SYNC_EVERY_POLLS_780 = 5


async def loop769():
    polls = 0
    while True:
        await asyncio.sleep(COMPLETION_POLL_SECONDS_780)
        if not configured769():
            continue
        polls = (polls + 1) % FULL_SYNC_EVERY_POLLS_780
        try:
            # At 5, 10, 15... minutes perform the existing full sync;
            # at the intervening minute marks import completions only.
            worker = sync_once769 if polls == 0 else sync_completions_once780
            await asyncio.to_thread(worker)
        except (GoogleTasksError769, OSError, ValueError):
            logger.warning("Google Tasks 769 sync deferred; review private status page")
