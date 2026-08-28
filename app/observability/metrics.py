from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class ExtractionMetrics:
    jobs_started: int = 0
    jobs_completed: int = 0
    jobs_failed: int = 0
    jobs_cache_hits: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    fallbacks: int = 0
    circuit_open_skips: int = 0
    total_duration_ms: int = 0
    total_cost_usd: float = 0.0
    extractor_successes: Counter[str] = field(default_factory=Counter)
    extractor_failures: Counter[str] = field(default_factory=Counter)
    page_latencies_ms: list[int] = field(default_factory=list)

    def record_job_started(self) -> None:
        self.jobs_started += 1

    def record_job_completed(
        self,
        *,
        duration_ms: int,
        cost_usd: float,
        cache_hit: bool,
        failed: bool,
    ) -> None:
        if failed:
            self.jobs_failed += 1
        else:
            self.jobs_completed += 1
        self.total_duration_ms += max(0, duration_ms)
        self.total_cost_usd += max(0.0, cost_usd)
        if cache_hit:
            self.jobs_cache_hits += 1

    def record_cache(self, *, hit: bool) -> None:
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    def record_extractor(self, extractor: str, *, success: bool) -> None:
        if success:
            self.extractor_successes[extractor] += 1
        else:
            self.extractor_failures[extractor] += 1

    def record_fallback(self) -> None:
        self.fallbacks += 1

    def record_circuit_open(self) -> None:
        self.circuit_open_skips += 1

    def record_page_latency(self, duration_ms: int) -> None:
        self.page_latencies_ms.append(max(0, duration_ms))

    def snapshot(self) -> dict[str, object]:
        latencies = sorted(self.page_latencies_ms)
        cache_total = self.cache_hits + self.cache_misses
        jobs_finished = self.jobs_completed + self.jobs_failed
        return {
            "jobs_started": self.jobs_started,
            "jobs_completed": self.jobs_completed,
            "jobs_failed": self.jobs_failed,
            "jobs_cache_hits": self.jobs_cache_hits,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": (self.cache_hits / cache_total) if cache_total else 0.0,
            "fallbacks": self.fallbacks,
            "circuit_open_skips": self.circuit_open_skips,
            "total_duration_ms": self.total_duration_ms,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "cost_per_1000_pages": _cost_per_thousand(self.total_cost_usd, len(latencies)),
            "pages_per_second": _pages_per_second(latencies, self.total_duration_ms),
            "page_latency_ms": {
                "count": len(latencies),
                "p50": _percentile(latencies, 50),
                "p95": _percentile(latencies, 95),
                "p99": _percentile(latencies, 99),
            },
            "extractor_successes": dict(self.extractor_successes),
            "extractor_failures": dict(self.extractor_failures),
            "job_success_rate": (self.jobs_completed / jobs_finished) if jobs_finished else 0.0,
        }


def _percentile(values: list[int], percentile: int) -> int:
    if not values:
        return 0
    index = min(len(values) - 1, max(0, int(round((percentile / 100) * (len(values) - 1)))))
    return values[index]


def _cost_per_thousand(cost_usd: float, page_count: int) -> float:
    if page_count <= 0:
        return 0.0
    return round((cost_usd / page_count) * 1000.0, 6)


def _pages_per_second(latencies: list[int], total_duration_ms: int) -> float:
    if total_duration_ms <= 0:
        return 0.0
    pages = len(latencies) or 0
    if pages <= 0:
        return 0.0
    return round(pages / (total_duration_ms / 1000.0), 4)


_METRICS = ExtractionMetrics()


def get_metrics() -> ExtractionMetrics:
    return _METRICS


def reset_metrics() -> None:
    global _METRICS
    _METRICS = ExtractionMetrics()
