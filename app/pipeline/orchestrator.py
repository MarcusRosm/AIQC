"""
Pipeline Orchestrator – sequences all 6 pipeline steps and emits SSE events.

This is the single entry-point for running the full AI-Driven QA pipeline.
It composes all pipeline components following the Open/Closed principle:
new steps can be added without modifying existing ones.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import QABaseError
from app.core.logging import get_logger
from app.core.schemas import (
    DiffResult,
    ExecutionResult,
    HealResult,
    HealStatus,
    PipelineEvent,
    PipelineRun,
    PipelineRunRequest,
    PipelineStage,
    TestStatus,
)
from app.healing.healer import SelfHealingEngine
from app.pipeline.code_generator import PlaywrightCodeGenerator
from app.pipeline.diff_analyzer import DiffAnalyzer
from app.pipeline.executor import PlaywrightExecutor
from app.pipeline.scenario_generator import ScenarioGenerator
from app.rag.retriever import ContextRetriever

logger = get_logger(__name__)


class PipelineOrchestrator:
    """
    Sequences Steps 1-6 and yields :class:`PipelineEvent` objects via an
    async generator suitable for direct SSE forwarding.

    Responsibilities: orchestration only.  All domain logic lives in the
    individual step components (dependency-injected).
    """

    def __init__(
        self,
        diff_analyzer: DiffAnalyzer | None = None,
        retriever: ContextRetriever | None = None,
        scenario_generator: ScenarioGenerator | None = None,
        code_generator: PlaywrightCodeGenerator | None = None,
        executor: PlaywrightExecutor | None = None,
        healer: SelfHealingEngine | None = None,
    ) -> None:
        self._diff_analyzer = diff_analyzer or DiffAnalyzer()
        self._retriever = retriever or ContextRetriever()
        self._scenario_gen = scenario_generator or ScenarioGenerator()
        self._code_gen = code_generator or PlaywrightCodeGenerator()
        self._executor = executor or PlaywrightExecutor()
        self._healer = healer or SelfHealingEngine()
        self._settings = get_settings()

    async def run(
        self, request: PipelineRunRequest
    ) -> AsyncIterator[PipelineEvent]:
        """
        Run the full pipeline, yielding progress events after each step.

        Args:
            request: The incoming pipeline run request.

        Yields:
            :class:`PipelineEvent` objects (stage, message, payload).
        """
        run = PipelineRun(
            run_id=str(uuid.uuid4()),
            label=request.run_label,
        )
        logger.info("Pipeline run started: %s", run.run_id)

        yield _event(PipelineStage.STARTED, "Pipeline initialised.", {"run_id": run.run_id})

        try:
            # ── Step 1: Diff Analysis ────────────────────────────────────────
            diff = self._diff_analyzer.analyze(request.diff_text)
            run.diff_result = diff
            yield _event(
                PipelineStage.DIFF_ANALYZED,
                f"Analysed {len(diff.files)} changed file(s).",
                diff.model_dump(exclude={"files": {"__all__": {"raw_diff"}}}),
            )

            # ── Step 2: RAG Retrieval ────────────────────────────────────────
            context = await self._retriever.retrieve(diff, top_k=self._settings.RAG_TOP_K)
            yield _event(
                PipelineStage.CONTEXT_RETRIEVED,
                f"Retrieved {len(context)} context snippet(s).",
                {"snippet_count": len(context)},
            )

            # ── Step 3: Scenario Generation ──────────────────────────────────
            scenario_list = await self._scenario_gen.generate(diff, context)
            run.scenario_list = scenario_list
            yield _event(
                PipelineStage.SCENARIOS_GENERATED,
                f"Generated {len(scenario_list.scenarios)} test scenario(s).",
                {
                    "count": len(scenario_list.scenarios),
                    "scenarios": [
                        {"id": s.id, "title": s.title, "category": s.category}
                        for s in scenario_list.scenarios
                    ],
                },
            )

            # ── Step 4: Code Generation ──────────────────────────────────────
            specs = await self._code_gen.generate(scenario_list, context, run.run_id)
            run.generated_specs = specs
            yield _event(
                PipelineStage.CODE_GENERATED,
                f"Generated {len(specs)} spec file(s).",
                {"spec_files": [s.filename for s in specs]},
            )

            # ── Step 5: Playwright Execution ─────────────────────────────────
            spec_paths = [
                Path(self._settings.GENERATED_TESTS_DIR) / run.run_id / s.filename
                for s in specs
            ]
            yield _event(PipelineStage.TESTS_RUNNING, "Playwright test suite starting…", {})
            execution_results = await self._executor.run(spec_paths)
            run.execution_results = execution_results

            failed_results = [r for r in execution_results if r.status == TestStatus.FAILED]
            locator_failures = [r for r in failed_results if r.failing_selector]

            # ── Step 6: Self-Healing ─────────────────────────────────────────
            heal_results: list[HealResult] = []
            if locator_failures and not request.skip_healing:
                yield _event(
                    PipelineStage.HEALING,
                    f"Attempting to heal {len(locator_failures)} broken locator(s)…",
                    {"count": len(locator_failures)},
                )
                for failure in locator_failures:
                    result = await self._healer.heal(failure)
                    heal_results.append(result)

            run.heal_results = heal_results
            run.status = PipelineStage.COMPLETED
            run.completed_at = datetime.utcnow()

            # Persist the run report
            self._save_report(run)

            summary = _build_summary(execution_results, heal_results)
            yield _event(PipelineStage.COMPLETED, summary, run.model_dump(mode="json"))

        except QABaseError as exc:
            logger.error("Pipeline error: %s", exc)
            run.status = PipelineStage.FAILED
            run.error = str(exc)
            self._save_report(run)
            yield _event(PipelineStage.FAILED, str(exc), {"error": str(exc)})
        except Exception as exc:
            logger.exception("Unexpected pipeline error")
            run.status = PipelineStage.FAILED
            run.error = str(exc)
            self._save_report(run)
            yield _event(PipelineStage.FAILED, f"Unexpected error: {exc}", {"error": str(exc)})

    async def retry_execution(
        self, run_id: str
    ) -> AsyncIterator[PipelineEvent]:
        """
        Manually retry the execution (Step 5 & 6) of a previously generated test run.
        """
        reports_dir = Path(self._settings.REPORTS_DIR)
        report_path = reports_dir / f"{run_id}.json"
        
        if not report_path.exists():
            yield _event(PipelineStage.FAILED, f"Report {run_id} not found.", {"error": "not_found"})
            return

        try:
            # 1. Load the existing report
            run_data = json.loads(report_path.read_text(encoding="utf-8"))
            run = PipelineRun.model_validate(run_data)
            
            logger.info("Pipeline retry started for: %s", run.run_id)
            yield _event(PipelineStage.STARTED, f"Manual retry initiated for {run.run_id}.", {"run_id": run.run_id})
            
            # Reset final statuses for retry
            run.status = PipelineStage.TESTS_RUNNING
            run.error = None

            if not run.generated_specs:
                raise QABaseError("No generated specs found to execute.")

            # ── Execute Step 5 ───────────────────────────────────────────────
            spec_paths = [
                Path(self._settings.GENERATED_TESTS_DIR) / run.run_id / s.filename
                for s in run.generated_specs
            ]
            yield _event(PipelineStage.TESTS_RUNNING, "Playwright test suite retrying…", {})
            execution_results = await self._executor.run(spec_paths)
            run.execution_results = execution_results

            failed_results = [r for r in execution_results if r.status == TestStatus.FAILED]
            locator_failures = [r for r in failed_results if r.failing_selector]

            # ── Execute Step 6 ───────────────────────────────────────────────
            heal_results: list[HealResult] = []
            if locator_failures:
                yield _event(
                    PipelineStage.HEALING,
                    f"Attempting to heal {len(locator_failures)} broken locator(s)…",
                    {"count": len(locator_failures)},
                )
                for failure in locator_failures:
                    result = await self._healer.heal(failure)
                    heal_results.append(result)

            run.heal_results = heal_results
            run.status = PipelineStage.COMPLETED
            run.completed_at = datetime.utcnow()

            # Resave the updated report
            self._save_report(run)

            summary = _build_summary(execution_results, heal_results)
            yield _event(PipelineStage.COMPLETED, summary, run.model_dump(mode="json"))

        except QABaseError as exc:
            logger.error("Pipeline retry error: %s", exc)
            yield _event(PipelineStage.FAILED, str(exc), {"error": str(exc)})
        except Exception as exc:
            logger.exception("Unexpected pipeline retry error")
            yield _event(PipelineStage.FAILED, f"Unexpected error: {exc}", {"error": str(exc)})


    def _save_report(self, run: PipelineRun) -> None:
        """Persist the run report as JSON to the reports directory."""
        reports_dir = Path(self._settings.REPORTS_DIR)
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"{run.run_id}.json"
        report_path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Run report saved: %s", report_path)


# ── helpers ───────────────────────────────────────────────────────────────────

def _event(stage: PipelineStage, message: str, payload: dict) -> PipelineEvent:
    return PipelineEvent(stage=stage, message=message, payload=payload)


def _build_summary(
    results: list[ExecutionResult], heals: list[HealResult]
) -> str:
    passed = sum(1 for r in results if r.status == TestStatus.PASSED)
    failed = sum(1 for r in results if r.status == TestStatus.FAILED)
    healed = sum(1 for h in heals if h.status == HealStatus.SUCCESS)
    hard = sum(1 for h in heals if h.status == HealStatus.HARD_FAILURE)
    return (
        f"Pipeline complete. Tests: {passed} passed, {failed} failed. "
        f"Healing: {healed} auto-fixed, {hard} hard failures."
    )
