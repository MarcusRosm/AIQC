"""
API Route: pipeline

API Route: pipeline

POST /api/pipeline/run           – start a new pipeline run
POST /api/pipeline/retry/{run_id} – manually retry an existing run's execution steps
GET  /api/pipeline/status/{run_id} – SSE stream of PipelineEvents
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.api.sse import create_bus, get_bus, remove_bus
from app.core.logging import get_logger
from app.core.schemas import PipelineRunRequest, PipelineStage
from app.pipeline.orchestrator import PipelineOrchestrator

logger = get_logger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/run", status_code=202)
async def start_run(
    body: PipelineRunRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Start a new pipeline run in the background.

    Returns the ``run_id`` immediately (202 Accepted).
    The client should then open GET /api/pipeline/status/{run_id} for SSE events.
    """
    orchestrator = PipelineOrchestrator()
    # A temporary orchestration is needed to get the run_id before starting
    # We'll use a simple UUID here and pass it consistently
    import uuid
    run_id = str(uuid.uuid4())

    bus = create_bus(run_id)
    background_tasks.add_task(_run_pipeline, orchestrator, body, run_id)
    logger.info("Pipeline run queued: %s", run_id)
    return {"run_id": run_id, "status": "queued"}


async def _run_pipeline(
    orchestrator: PipelineOrchestrator,
    request: PipelineRunRequest,
    run_id: str,
) -> None:
    """Background task: drive the pipeline generator and push to the bus."""
    bus = get_bus(run_id)
    if bus is None:
        logger.error("Bus for run %s not found.", run_id)
        return

    try:
        async for event in orchestrator.run(request):
            await bus.put(event)
            if event.stage in (PipelineStage.COMPLETED, PipelineStage.FAILED):
                break
    except Exception as exc:
        logger.exception("Pipeline background task error: %s", exc)
    finally:
        await bus.close()
        # Keep bus around briefly so late-connecting clients get the close
        await asyncio.sleep(5)
        remove_bus(run_id)


@router.post("/retry/{run_id}", status_code=202)
async def retry_run(
    run_id: str,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Retry a previous pipeline run (skips generation, just re-runs tests + heals).
    
    Returns 202 Accepted. The client should open GET /api/pipeline/status/{run_id}.
    """
    orchestrator = PipelineOrchestrator()
    bus = create_bus(run_id)
    background_tasks.add_task(_retry_pipeline, orchestrator, run_id)
    logger.info("Pipeline retry queued: %s", run_id)
    return {"run_id": run_id, "status": "queued"}


async def _retry_pipeline(
    orchestrator: PipelineOrchestrator,
    run_id: str,
) -> None:
    """Background task: drive the pipeline retry and push to the bus."""
    bus = get_bus(run_id)
    if bus is None:
        logger.error("Bus for retry run %s not found.", run_id)
        return

    try:
        async for event in orchestrator.retry_execution(run_id):
            await bus.put(event)
            if event.stage in (PipelineStage.COMPLETED, PipelineStage.FAILED):
                break
    except Exception as exc:
        logger.exception("Pipeline retry background task error: %s", exc)
    finally:
        await bus.close()
        await asyncio.sleep(5)
        remove_bus(run_id)


@router.get("/status/{run_id}")
async def stream_status(run_id: str) -> EventSourceResponse:
    """
    Server-Sent Events stream for a specific pipeline run.

    Clients should connect with ``EventSource('/api/pipeline/status/<run_id>')``.
    """
    bus = get_bus(run_id)
    if bus is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found or already completed.")

    async def event_generator():
        async for event in bus:
            yield {
                "event": event.stage.value,
                "data": event.model_dump_json(),
            }

    return EventSourceResponse(event_generator())
