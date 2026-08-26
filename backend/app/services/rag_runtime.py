from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar
from urllib.parse import urlparse, urlunparse

from qdrant_client.http.exceptions import ResponseHandlingException

T = TypeVar("T")

TRANSIENT_RETRIEVAL_ERRORS = (
    ResponseHandlingException,
    ConnectionError,
    TimeoutError,
    OSError,
)


def normalize_qdrant_url(url: str) -> str:
    """Ensure Qdrant Cloud REST URLs include the standard :6333 port."""
    cleaned = url.strip().rstrip("/")
    if not cleaned:
        return cleaned

    parsed = urlparse(cleaned)
    if parsed.scheme in {"http", "https"} and parsed.hostname and parsed.port is None:
        netloc = f"{parsed.hostname}:6333"
        return urlunparse(
            (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
        )
    return cleaned


def call_with_retries(
    operation: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay_seconds: float = 0.75,
) -> T:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return operation()
        except TRANSIENT_RETRIEVAL_ERRORS as error:
            last_error = error
            if attempt + 1 >= attempts:
                break
            time.sleep(base_delay_seconds * (attempt + 1))
    assert last_error is not None
    raise last_error
