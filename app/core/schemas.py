"""
Shared Pydantic v2 schemas used across all pipeline stages.

These dataclasses form the typed contract between pipeline components.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class TestCategory(str, Enum):
    HAPPY_PATH = "happy_path"
    NEGATIVE = "negative"
    EDGE_CASE = "edge_case"
    SECURITY = "security"


class PipelineStage(str, Enum):
    STARTED = "started"
    DIFF_ANALYZED = "diff_analyzed"
    CONTEXT_RETRIEVED = "context_retrieved"
    SCENARIOS_GENERATED = "scenarios_generated"
    CODE_GENERATED = "code_generated"
    TESTS_RUNNING = "tests_running"
    HEALING = "healing"
    COMPLETED = "completed"
    FAILED = "failed"


class HealStatus(str, Enum):
    SUCCESS = "success"
    HARD_FAILURE = "hard_failure"
    SKIPPED = "skipped"


class TestStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


# ── Diff Analysis ─────────────────────────────────────────────────────────────

class FileChange(BaseModel):
    """Represents a single file changed in the diff."""

    path: str
    change_type: str  # "modified" | "added" | "deleted" | "renamed"
    additions: int = 0
    deletions: int = 0
    functions_touched: list[str] = Field(default_factory=list)
    classes_touched: list[str] = Field(default_factory=list)
    raw_diff: str = ""


class DiffResult(BaseModel):
    """Parsed result of a git diff analysis."""

    files: list[FileChange] = Field(default_factory=list)
    summary: str = ""
    total_additions: int = 0
    total_deletions: int = 0
    affected_routes: list[str] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)


# ── Test Scenarios ────────────────────────────────────────────────────────────

class TestStep(BaseModel):
    """A single step within a test scenario."""

    action: str
    selector: str | None = None
    value: str | None = None
    assertion: str | None = None


class TestScenario(BaseModel):
    """A single generated test scenario."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    category: TestCategory
    description: str
    preconditions: list[str] = Field(default_factory=list)
    steps: list[TestStep] = Field(default_factory=list)
    expected_result: str = ""
    tags: list[str] = Field(default_factory=list)


class TestScenarioList(BaseModel):
    """Collection of generated test scenarios."""

    scenarios: list[TestScenario] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    source_diff_summary: str = ""


# ── Code Generation ───────────────────────────────────────────────────────────

class GeneratedSpec(BaseModel):
    """A generated Playwright .spec.ts file."""

    filename: str
    content: str
    scenario_ids: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Test Execution ────────────────────────────────────────────────────────────

class ExecutionResult(BaseModel):
    """Result of a single test execution."""

    test_title: str
    spec_file: str
    status: TestStatus
    duration_ms: int = 0
    error_message: str | None = None
    failing_selector: str | None = None
    dom_snapshot: str | None = None
    screenshot_path: str | None = None


# ── Self-Healing ──────────────────────────────────────────────────────────────

class HealCandidate(BaseModel):
    """A candidate locator for healing a broken selector."""

    selector: str
    playwright_locator: str
    confidence: float = Field(ge=0.0, le=1.0)
    match_reasons: list[str] = Field(default_factory=list)


class HealResult(BaseModel):
    """Result of a self-healing attempt."""

    original_selector: str
    status: HealStatus
    chosen_candidate: HealCandidate | None = None
    all_candidates: list[HealCandidate] = Field(default_factory=list)
    pr_comment: str | None = None
    test_title: str = ""
    healed_at: datetime = Field(default_factory=datetime.utcnow)


# ── Pipeline ──────────────────────────────────────────────────────────────────

class PipelineRunRequest(BaseModel):
    """Request to start a new pipeline run."""

    diff_text: str = Field(..., description="Raw git diff text to analyse")
    repo_root: str | None = Field(None, description="Absolute path to repo root for RAG indexing")
    run_label: str | None = None
    skip_healing: bool = False


class PipelineEvent(BaseModel):
    """An SSE event emitted during pipeline execution."""

    stage: PipelineStage
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PipelineRun(BaseModel):
    """Complete record of a pipeline run stored on disk."""

    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    status: PipelineStage = PipelineStage.STARTED
    diff_result: DiffResult | None = None
    scenario_list: TestScenarioList | None = None
    generated_specs: list[GeneratedSpec] = Field(default_factory=list)
    execution_results: list[ExecutionResult] = Field(default_factory=list)
    heal_results: list[HealResult] = Field(default_factory=list)
    error: str | None = None
