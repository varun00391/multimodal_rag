from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass
from enum import Enum

from app.config import Settings

MANAGED_EXTRACTORS = ("gemini", "groq-vision")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitStats:
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    opened_at: float | None = None
    last_failure_at: float | None = None


class ProviderCircuitBreaker:
    """Fails managed extractors fast after repeated provider errors.

    Local extractors are never tripped. An open circuit returns a structured
    error so other groups in the same job can still complete.
    """

    def __init__(self, settings: Settings) -> None:
        self._threshold = max(1, settings.extraction_circuit_failure_threshold)
        self._recovery_seconds = max(0.0, settings.extraction_circuit_recovery_seconds)
        self._stats: dict[str, CircuitStats] = {
            name: CircuitStats() for name in MANAGED_EXTRACTORS
        }

    def allow(self, extractor: str) -> bool:
        stats = self._stats.get(extractor)
        if stats is None:
            return True
        self._refresh(stats)
        return stats.state != CircuitState.OPEN

    def record_success(self, extractor: str) -> None:
        stats = self._stats.get(extractor)
        if stats is None:
            return
        stats.consecutive_failures = 0
        stats.opened_at = None
        stats.state = CircuitState.CLOSED

    def record_failure(self, extractor: str) -> None:
        stats = self._stats.get(extractor)
        if stats is None:
            return
        stats.consecutive_failures += 1
        stats.last_failure_at = time.monotonic()
        if stats.state == CircuitState.HALF_OPEN or stats.consecutive_failures >= self._threshold:
            stats.state = CircuitState.OPEN
            stats.opened_at = stats.last_failure_at

    def snapshot(self) -> dict[str, dict[str, object]]:
        for stats in self._stats.values():
            self._refresh(stats)
        return {
            name: {
                "state": stats.state.value,
                "consecutive_failures": stats.consecutive_failures,
            }
            for name, stats in self._stats.items()
        }

    def _refresh(self, stats: CircuitStats) -> None:
        if stats.state != CircuitState.OPEN or stats.opened_at is None:
            return
        if self._recovery_seconds <= 0:
            return
        if time.monotonic() - stats.opened_at >= self._recovery_seconds:
            stats.state = CircuitState.HALF_OPEN


class JobLimiter:
    """Bounds accepted and concurrently running extraction jobs."""

    def __init__(self, settings: Settings) -> None:
        self._max_inflight = max(1, settings.extraction_max_inflight_jobs)
        self._semaphore = asyncio.Semaphore(max(1, settings.extraction_max_concurrent_jobs))
        self._inflight = 0
        self._lock = threading.Lock()

    @property
    def inflight(self) -> int:
        return self._inflight

    @property
    def max_inflight(self) -> int:
        return self._max_inflight

    def try_accept(self) -> bool:
        with self._lock:
            if self._inflight >= self._max_inflight:
                return False
            self._inflight += 1
            return True

    def release_accepted(self) -> None:
        with self._lock:
            if self._inflight > 0:
                self._inflight -= 1

    def slot(self) -> _SemaphoreSlot:
        return _SemaphoreSlot(self._semaphore)


@dataclass
class _SemaphoreSlot:
    semaphore: asyncio.Semaphore

    async def __aenter__(self) -> None:
        await self.semaphore.acquire()
        return None

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.semaphore.release()


_LIMITER: JobLimiter | None = None
_BREAKER: ProviderCircuitBreaker | None = None


def get_job_limiter(settings: Settings) -> JobLimiter:
    global _LIMITER
    if _LIMITER is None:
        _LIMITER = JobLimiter(settings)
    return _LIMITER


def get_circuit_breaker(settings: Settings) -> ProviderCircuitBreaker:
    global _BREAKER
    if _BREAKER is None:
        _BREAKER = ProviderCircuitBreaker(settings)
    return _BREAKER


def reset_runtime_limits() -> None:
    global _LIMITER, _BREAKER
    _LIMITER = None
    _BREAKER = None
