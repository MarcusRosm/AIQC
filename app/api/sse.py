"""
SSE Event Bus.

A simple asyncio-Queue-based broadcaster that allows the pipeline orchestrator
to push events and the SSE route to stream them to the client.

Each run gets its own :class:`RunEventBus` instance, stored in a global registry.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import AsyncIterator

from app.core.schemas import PipelineEvent


class RunEventBus:
    """
    Per-run asyncio Queue that bridges the pipeline generator and the SSE endpoint.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[PipelineEvent | None] = asyncio.Queue()

    async def put(self, event: PipelineEvent) -> None:
        await self._queue.put(event)

    async def close(self) -> None:
        """Signal the consumer that the stream has ended."""
        await self._queue.put(None)

    async def __aiter__(self) -> AsyncIterator[PipelineEvent]:
        while True:
            event = await self._queue.get()
            if event is None:
                break
            yield event


# Global registry of active run buses
_bus_registry: dict[str, RunEventBus] = {}


def create_bus(run_id: str) -> RunEventBus:
    bus = RunEventBus()
    _bus_registry[run_id] = bus
    return bus


def get_bus(run_id: str) -> RunEventBus | None:
    return _bus_registry.get(run_id)


def remove_bus(run_id: str) -> None:
    _bus_registry.pop(run_id, None)
