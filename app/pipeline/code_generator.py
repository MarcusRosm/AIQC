"""
Step 4 – Python Pytest Playwright Code Generator.

Translates a :class:`TestScenarioList` into executable ``test_*.py`` files
ready for direct pytest execution.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import LLMError
from app.core.logging import get_logger
from app.core.schemas import GeneratedSpec, TestScenarioList
from app.llm.client import LLMClient
from app.llm.prompts import SYSTEM_QA_ARCHITECT, code_generation_prompt

logger = get_logger(__name__)

_MAX_SCENARIOS_PER_FILE = 10


class PlaywrightCodeGenerator:
    """
    Step 4: Converts test scenarios to runnable Python Pytest Playwright specs.

    Large scenario lists are split across multiple spec files to keep
    each file focused and individually executable.
    """

    def __init__(self, llm: LLMClient | None = None) -> None:
        self._llm = llm or LLMClient()

    async def generate(
        self,
        scenarios: TestScenarioList,
        context: list[str],
        run_id: str,
    ) -> list[GeneratedSpec]:
        """
        Generate ``test_*.py`` files from the given scenario list.

        Args:
            scenarios: Scenarios produced by :class:`ScenarioGenerator`.
            context: Repository context snippets from the RAG layer.
            run_id: Pipeline run ID used for directory naming.

        Returns:
            A list of :class:`GeneratedSpec` objects with filename + content.
        """
        chunks = self._chunk_scenarios(scenarios)
        specs: list[GeneratedSpec] = []

        for idx, chunk in enumerate(chunks):
            logger.info(
                "Generating spec file %d/%d (%d scenarios)",
                idx + 1, len(chunks), len(chunk.scenarios),
            )
            spec = await self._generate_one(chunk, context, idx)
            specs.append(spec)
            self._write_spec(spec, run_id)

        logger.info("Code generation complete: %d spec file(s)", len(specs))
        return specs

    async def _generate_one(
        self,
        chunk: TestScenarioList,
        context: list[str],
        index: int,
    ) -> GeneratedSpec:
        prompt = code_generation_prompt(chunk, context)
        last_error: Exception | None = None
        for attempt in range(1, 3):
            try:
                raw = await self._llm.generate_json(prompt, system=SYSTEM_QA_ARCHITECT)
                content = raw.get("content", "")
                filename = raw.get("filename", f"test_generated_{index}.py")
                if not content:
                    raise LLMError("LLM returned empty spec content.")
                # Clean up escaped newlines from JSON string
                content = content.replace("\\n", "\n").replace("\\t", "    ")
                return GeneratedSpec(
                    filename=filename,
                    content=content,
                    scenario_ids=[s.id for s in chunk.scenarios],
                )
            except (LLMError, KeyError) as exc:
                logger.warning("Code gen attempt %d failed: %s", attempt, exc)
                last_error = exc

        raise LLMError(
            "Code generation failed after all retries.",
            detail=str(last_error),
        )

    @staticmethod
    def _chunk_scenarios(scenarios: TestScenarioList) -> list[TestScenarioList]:
        """Split a large scenario list into smaller chunks."""
        all_scens = scenarios.scenarios
        chunks: list[TestScenarioList] = []
        for i in range(0, max(1, len(all_scens)), _MAX_SCENARIOS_PER_FILE):
            batch = all_scens[i : i + _MAX_SCENARIOS_PER_FILE]
            chunks.append(
                TestScenarioList(
                    scenarios=batch,
                    source_diff_summary=scenarios.source_diff_summary,
                )
            )
        return chunks

    @staticmethod
    def _write_spec(spec: GeneratedSpec, run_id: str) -> None:
        """Persist the spec file to the generated_tests directory."""
        settings = get_settings()
        out_dir = Path(settings.GENERATED_TESTS_DIR) / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / spec.filename
        out_path.write_text(spec.content, encoding="utf-8")
        logger.info("Spec written: %s", out_path)
