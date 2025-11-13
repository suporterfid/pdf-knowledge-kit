"""Threaded ingestion runner with cancel support."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event
from uuid import UUID


class IngestionRunner:
    """Simple wrapper around :class:`ThreadPoolExecutor` to manage jobs.

    Each submitted job gets an associated :class:`threading.Event` used as a
    cancellation flag. Worker functions receive this event as the first
    positional argument and are expected to periodically check
    ``cancel_event.is_set()`` between batches of work and abort early when set.
    """

    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._events: dict[UUID, Event] = {}
        self._futures: dict[UUID, Future] = {}

    # Worker function signature
    Worker = Callable[[Event], None]

    def submit(self, job_id: UUID, fn: Worker) -> Future:
        """Submit a job for execution."""
        cancel_event = Event()
        self._events[job_id] = cancel_event
        future = self.executor.submit(fn, cancel_event)
        self._futures[job_id] = future
        return future

    # Cancel job
    def cancel(self, job_id: UUID) -> None:
        event = self._events.get(job_id)
        if event:
            event.set()
        fut = self._futures.get(job_id)
        if fut:
            fut.cancel()

    def clear(self, job_id: UUID) -> None:
        """Remove references for a finished or cancelled job."""
        self._events.pop(job_id, None)
        self._futures.pop(job_id, None)

    def get(self, job_id: UUID) -> Future | None:
        return self._futures.get(job_id)

    def list(self) -> Iterable[UUID]:
        return list(self._futures)
