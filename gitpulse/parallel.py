"""
parallel.py — Thread-pool fan-out helper for GitPulse.

Provides a simple run_parallel() utility that fans a function out over a list
of items using a bounded thread pool. Used by digest, bulk-ops, and stale-branch
features to avoid blocking the Textual main thread.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def run_parallel(
    fn: Callable[[T], R],
    items: list[T],
    max_workers: int = 8,
    on_progress: Callable[[int, int, T, R | Exception], None] | None = None,
) -> list[tuple[T, R | Exception]]:
    """Fan *fn* out over *items* using a thread pool, return ordered results.

    Args:
        fn: Callable taking one item, returning a result.
        items: List of inputs to process.
        max_workers: Thread-pool ceiling (default 8).
        on_progress: Optional callback invoked after each future completes.
            Called with (completed_count, total_count, item, result_or_exception).
            Fires from worker threads — UI consumers must marshal via
            ``app.call_from_thread``.

    Returns:
        List of ``(item, result)`` tuples in the same order as *items*.
        If *fn* raises, the exception is captured and stored as the result
        rather than propagated, so all items are always represented.
    """
    if not items:
        return []

    total = len(items)
    results: dict[int, R | Exception] = {}

    with ThreadPoolExecutor(max_workers=min(max_workers, total)) as pool:
        future_to_idx = {pool.submit(fn, item): i for i, item in enumerate(items)}
        completed = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            item = items[idx]
            try:
                result: R | Exception = future.result()
            except Exception as exc:
                result = exc
            results[idx] = result
            completed += 1
            if on_progress is not None:
                on_progress(completed, total, item, result)

    return [(items[i], results[i]) for i in range(total)]
