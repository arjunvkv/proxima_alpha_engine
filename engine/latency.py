"""Small timing primitives for live MT5 telemetry."""

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class TimedResult(Generic[T]):
    """A call result paired with elapsed time for successful snapshots."""

    value: T | None
    latency_ms: float | None


def measure_call_latency(call: Callable[[], T | None]) -> TimedResult[T]:
    """Measure a snapshot call and keep latency blank when no snapshot is returned."""
    started_at = perf_counter()
    value = call()
    if value is None:
        return TimedResult(value=None, latency_ms=None)
    return TimedResult(
        value=value,
        latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
    )
