"""Release 494: bounded Open Food Facts reads with retry, TTL and backoff.

No database reads/writes. The in-process cache is best-effort: it reduces
repeat traffic but is deliberately not an inter-host or inter-worker quota.
Never log the food name, barcode, URL, cookies, or response body.
"""

from collections import OrderedDict, deque
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import logging
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

LOGGER = logging.getLogger(__name__)
MAX_RESPONSE = 2 * 1024 * 1024
MAX_ENTRIES = 256
KIND_BUDGET = {
    "name-legacy": 8,
    "name-modern": 8,
    "barcode": 12,
}
ALLOWED = {
    "name-legacy": ("world.openfoodfacts.org", "/cgi/search.pl"),
    "name-modern": ("search.openfoodfacts.org", "/search"),
    "barcode": ("world.openfoodfacts.org", "/api/v2/product/"),
}
LOCK = threading.RLock()
CACHE = OrderedDict()
HISTORY = {kind: deque() for kind in KIND_BUDGET}
COOLDOWN = {kind: 0.0 for kind in KIND_BUDGET}
USER_AGENT = "TrackerFoodJournal/0.4 (https://tracker.rehmert.net)"


class OFFFailure494(Exception):
    def __init__(self, reason, status=None, retry_after=None):
        self.reason = reason
        self.status = status
        self.retry_after = retry_after
        super().__init__(reason)


def _retry_after494(headers):
    raw = headers.get("Retry-After", "") if headers else ""
    try:
        seconds = float(raw)
        if 1 <= seconds <= 600:
            return int(seconds)
    except (TypeError, ValueError):
        pass
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        seconds = (parsed - datetime.now(timezone.utc)).total_seconds()
        if seconds > 0:
            return max(1, min(600, int(seconds) + 1))
    except (TypeError, ValueError, OverflowError, IndexError):
        pass
    return 60


def _reserve494(kind):
    now = time.monotonic()
    with LOCK:
        if COOLDOWN[kind] > now:
            raise OFFFailure494(
                "cooldown", retry_after=max(1, int(COOLDOWN[kind] - now) + 1)
            )
        events = HISTORY[kind]
        while events and events[0] <= now - 60:
            events.popleft()
        if len(events) >= KIND_BUDGET[kind]:
            raise OFFFailure494(
                "local_limit",
                retry_after=max(1, int(events[0] + 60 - now) + 1),
            )
        events.append(now)


def _cooldown494(kind, seconds):
    with LOCK:
        COOLDOWN[kind] = max(COOLDOWN[kind], time.monotonic() + seconds)


def _valid_url494(url, kind):
    if kind not in ALLOWED or not isinstance(url, str):
        raise ValueError("Unsupported upstream lookup")
    parsed = urlsplit(url)
    host, path = ALLOWED[kind]
    if (
        parsed.scheme != "https"
        or parsed.hostname != host
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or (not parsed.path.startswith(path)
            if kind == "barcode" else parsed.path != path)
    ):
        raise ValueError("Unsupported upstream URL")


def fetch_json494(url, kind, *, timeout=7, ttl=900, retry=True):
    """Fetch an allowlisted URL; throttle, cache and retry transient errors.

    A failing upstream cannot make us issue unlimited requests. HTTP 429
    triggers a cooldown, never an immediate retry. Only valid JSON objects
    are cached, with a monotonic expiry.
    """
    _valid_url494(url, kind)
    if not (1 <= timeout <= 15 and 10 <= ttl <= 86400):
        raise ValueError("Invalid upstream read limits")

    key = (kind, url)
    with LOCK:
        cached = CACHE.get(key)
        if cached is not None:
            expires, document = cached
            if time.monotonic() < expires:
                CACHE.move_to_end(key)
                return document
            CACHE.pop(key, None)

    attempts = 2 if retry else 1
    for attempt in range(attempts):
        _reserve494(kind)
        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise OFFFailure494("oversized")
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise OFFFailure494("bad_json")
        except HTTPError as exc:
            status = exc.code
            if status == 429:
                delay = _retry_after494(exc.headers)
                _cooldown494(kind, delay)
                LOGGER.warning("OFF read throttled kind=%s http=%s", kind, status)
                raise OFFFailure494(
                    "rate_limited", status=status, retry_after=delay
                ) from None
            if 500 <= status <= 599 and attempt + 1 < attempts:
                time.sleep(0.4)
                continue
            if 500 <= status <= 599:
                # Legacy CGI search often experiences prolonged 503s.
                # A longer circuit break avoids hammering that backend.
                _cooldown494(kind, 180 if kind == "name-legacy" else 30)
            LOGGER.warning("OFF read failed kind=%s http=%s", kind, status)
            raise OFFFailure494(
                "not_found" if status == 404 else "upstream_http",
                status=status,
            ) from None
        except (URLError, TimeoutError, OSError, ValueError):
            if attempt + 1 < attempts:
                time.sleep(0.4)
                continue
            _cooldown494(kind, 20)
            LOGGER.warning("OFF read failed kind=%s cause=network_or_json", kind)
            raise OFFFailure494("unavailable") from None
        except OFFFailure494:
            LOGGER.warning("OFF read failed kind=%s cause=response_limits", kind)
            raise
        else:
            with LOCK:
                CACHE[key] = (time.monotonic() + ttl, payload)
                CACHE.move_to_end(key)
                while len(CACHE) > MAX_ENTRIES:
                    CACHE.popitem(last=False)
            return payload

    raise OFFFailure494("unavailable")


def reset_for_tests494():
    """Test-only: reset process-local caches, request budgets and cooldowns."""
    with LOCK:
        CACHE.clear()
        for events in HISTORY.values():
            events.clear()
        for kind in COOLDOWN:
            COOLDOWN[kind] = 0.0
