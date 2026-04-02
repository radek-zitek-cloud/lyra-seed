"""Retry helpers for LLM API calls — exponential backoff with jitter."""

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable

import httpx

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


async def async_retry(
    coro_factory: Callable[[], Awaitable[httpx.Response]],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
) -> httpx.Response:
    """Retry an async HTTP call with exponential backoff.

    Retries on:
    - HTTP 429 (rate limit), 502, 503, 504 (gateway errors)
    - httpx.TimeoutException
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            resp = await coro_factory()
            if resp.status_code in RETRYABLE_STATUS_CODES:
                if attempt < max_retries:
                    delay = _backoff_delay(attempt, base_delay, max_delay)
                    logger.warning(
                        "HTTP %d, retrying in %.1fs (attempt %d/%d)",
                        resp.status_code,
                        delay,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(delay)
                    continue
            return resp
        except httpx.TimeoutException as e:
            last_exception = e
            if attempt < max_retries:
                delay = _backoff_delay(attempt, base_delay, max_delay)
                logger.warning(
                    "Timeout, retrying in %.1fs (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(delay)
            else:
                raise

    raise last_exception  # type: ignore[misc]


def sync_retry(
    func: Callable[[], httpx.Response],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
) -> httpx.Response:
    """Retry a sync HTTP call with exponential backoff."""
    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            resp = func()
            if resp.status_code in RETRYABLE_STATUS_CODES:
                if attempt < max_retries:
                    delay = _backoff_delay(attempt, base_delay, max_delay)
                    logger.warning(
                        "HTTP %d, retrying in %.1fs (attempt %d/%d)",
                        resp.status_code,
                        delay,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(delay)
                    continue
            return resp
        except httpx.TimeoutException as e:
            last_exception = e
            if attempt < max_retries:
                delay = _backoff_delay(attempt, base_delay, max_delay)
                logger.warning(
                    "Timeout, retrying in %.1fs (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(delay)
            else:
                raise

    raise last_exception  # type: ignore[misc]


def _backoff_delay(attempt: int, base_delay: float, max_delay: float) -> float:
    """Calculate delay with exponential backoff + jitter."""
    delay = base_delay * (2**attempt) + random.uniform(0, 0.5)
    return min(delay, max_delay)
