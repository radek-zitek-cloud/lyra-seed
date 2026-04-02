"""Retry helpers for LLM API calls — exponential backoff with jitter.

Defaults are set by configure() from lyra.config.json on startup.
Per-agent overrides can be passed via parameters.
"""

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable

import httpx

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 502, 503, 504}

# Module-level defaults — set by configure() on startup,
# can be overridden per-call via parameters.
_default_max_retries: int = 3
_default_base_delay: float = 1.0
_default_max_delay: float = 30.0


def configure(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
) -> None:
    """Set default retry parameters from platform config."""
    global _default_max_retries, _default_base_delay, _default_max_delay
    _default_max_retries = max_retries
    _default_base_delay = base_delay
    _default_max_delay = max_delay


async def async_retry(
    coro_factory: Callable[[], Awaitable[httpx.Response]],
    max_retries: int | None = None,
    base_delay: float | None = None,
    max_delay: float | None = None,
) -> httpx.Response:
    """Retry an async HTTP call with exponential backoff.

    Uses module-level defaults if parameters are not provided.
    Retries on HTTP 429/502/503/504 and httpx.TimeoutException.
    """
    _retries = max_retries if max_retries is not None else _default_max_retries
    _base = base_delay if base_delay is not None else _default_base_delay
    _max = max_delay if max_delay is not None else _default_max_delay
    last_exception: Exception | None = None

    for attempt in range(_retries + 1):
        try:
            resp = await coro_factory()
            if resp.status_code in RETRYABLE_STATUS_CODES:
                if attempt < _retries:
                    delay = _backoff_delay(attempt, _base, _max)
                    logger.warning(
                        "HTTP %d, retrying in %.1fs (attempt %d/%d)",
                        resp.status_code,
                        delay,
                        attempt + 1,
                        _retries,
                    )
                    await asyncio.sleep(delay)
                    continue
            return resp
        except httpx.TimeoutException as e:
            last_exception = e
            if attempt < _retries:
                delay = _backoff_delay(attempt, _base, _max)
                logger.warning(
                    "Timeout, retrying in %.1fs (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    _retries,
                )
                await asyncio.sleep(delay)
            else:
                raise

    raise last_exception  # type: ignore[misc]


def sync_retry(
    func: Callable[[], httpx.Response],
    max_retries: int | None = None,
    base_delay: float | None = None,
    max_delay: float | None = None,
) -> httpx.Response:
    """Retry a sync HTTP call with exponential backoff."""
    _retries = max_retries if max_retries is not None else _default_max_retries
    _base = base_delay if base_delay is not None else _default_base_delay
    _max = max_delay if max_delay is not None else _default_max_delay
    last_exception: Exception | None = None

    for attempt in range(_retries + 1):
        try:
            resp = func()
            if resp.status_code in RETRYABLE_STATUS_CODES:
                if attempt < _retries:
                    delay = _backoff_delay(attempt, _base, _max)
                    logger.warning(
                        "HTTP %d, retrying in %.1fs (attempt %d/%d)",
                        resp.status_code,
                        delay,
                        attempt + 1,
                        _retries,
                    )
                    time.sleep(delay)
                    continue
            return resp
        except httpx.TimeoutException as e:
            last_exception = e
            if attempt < _retries:
                delay = _backoff_delay(attempt, _base, _max)
                logger.warning(
                    "Timeout, retrying in %.1fs (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    _retries,
                )
                time.sleep(delay)
            else:
                raise

    raise last_exception  # type: ignore[misc]


def _backoff_delay(attempt: int, base_delay: float, max_delay: float) -> float:
    """Calculate delay with exponential backoff + jitter."""
    delay = base_delay * (2**attempt) + random.uniform(0, 0.5)
    return min(delay, max_delay)
