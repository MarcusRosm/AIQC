"""
API Route: reports

GET /api/reports           – list all completed pipeline runs
GET /api/reports/{run_id}  – full run details
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.schemas import PipelineRun

logger = get_logger(__name__)
router = APIRouter(prefix="/api/reports", tags=["reports"])


def _reports_dir() -> Path:
    return Path(get_settings().REPORTS_DIR)


@router.get("")
async def list_reports() -> list[dict]:
    """Return a summary list of all pipeline runs (sorted newest first)."""
    reports_dir = _reports_dir()
    if not reports_dir.exists():
        return []

    summaries: list[dict] = []
    for report_path in sorted(reports_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            summaries.append({
                "run_id": data.get("run_id"),
                "label": data.get("label"),
                "status": data.get("status"),
                "started_at": data.get("started_at"),
                "completed_at": data.get("completed_at"),
                "test_count": len(data.get("execution_results", [])),
                "heal_count": len(data.get("heal_results", [])),
            })
        except Exception as exc:
            logger.warning("Failed to read report %s: %s", report_path.name, exc)

    return summaries


@router.get("/{run_id}")
async def get_report(run_id: str) -> PipelineRun:
    """Return the full details for a specific run."""
    report_path = _reports_dir() / f"{run_id}.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail=f"Report '{run_id}' not found.")
    try:
        return PipelineRun.model_validate_json(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse report: {exc}") from exc


@router.delete("/{run_id}", status_code=204)
async def delete_report(run_id: str) -> None:
    """Delete a run report."""
    report_path = _reports_dir() / f"{run_id}.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail=f"Report '{run_id}' not found.")
    report_path.unlink()
