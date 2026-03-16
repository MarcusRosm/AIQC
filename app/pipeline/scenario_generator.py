"""
Step 3 – AI Test Scenario Generator.

Orchestrates the LLM call to produce a structured TestScenarioList from
a DiffResult and a list of repository context snippets.
"""

from __future__ import annotations

from app.core.exceptions import LLMError
from app.core.logging import get_logger
from app.core.schemas import (
    DiffResult,
    TestCategory,
    TestScenario,
    TestScenarioList,
    TestStep,
)
from app.llm.client import LLMClient
from app.llm.prompts import SYSTEM_QA_ARCHITECT, scenario_generation_prompt

logger = get_logger(__name__)


class ScenarioGenerator:
    """
    Step 3: Generates structured test scenarios via the local LLM.

    Parses the LLM's JSON response into a typed :class:`TestScenarioList`,
    handling partial or malformed responses gracefully.
    """

    def __init__(self, llm: LLMClient | None = None) -> None:
        self._llm = llm or LLMClient()

    async def generate(
        self, diff: DiffResult, context: list[str]
    ) -> TestScenarioList:
        """
        Generate test scenarios for the given diff and context.

        Args:
            diff: Parsed diff analysis from :class:`DiffAnalyzer`.
            context: Retrieved code snippets from :class:`ContextRetriever`.

        Returns:
            A populated :class:`TestScenarioList`.

        Raises:
            :exc:`LLMError`: If the LLM returns unparsable output after retries.
        """
        prompt = scenario_generation_prompt(diff, context)
        logger.info("Requesting scenario generation from LLM (model context: %d chars)", len(prompt))

        last_error: Exception | None = None
        for attempt in range(1, 3):
            try:
                raw = await self._llm.generate_json(
                    prompt, system=SYSTEM_QA_ARCHITECT
                )
                scenarios_list = self._parse_response(raw, diff.summary)
                logger.info(
                    "Generated %d scenarios (attempt %d)", len(scenarios_list.scenarios), attempt
                )
                return scenarios_list
            except (LLMError, KeyError, ValueError) as exc:
                logger.warning("Scenario generation attempt %d failed: %s", attempt, exc)
                last_error = exc

        raise LLMError(
            "Scenario generation failed after all retries.",
            detail=str(last_error),
        )

    @staticmethod
    def _parse_response(raw: dict, diff_summary: str) -> TestScenarioList:
        """Parse the LLM JSON into a :class:`TestScenarioList`."""
        raw_scenarios = raw.get("scenarios", [])
        if not isinstance(raw_scenarios, list):
            raise ValueError(f"'scenarios' key is not a list: {type(raw_scenarios)}")

        scenarios: list[TestScenario] = []
        for item in raw_scenarios:
            if not isinstance(item, dict):
                continue
            try:
                category = TestCategory(item.get("category", "happy_path"))
            except ValueError:
                category = TestCategory.HAPPY_PATH

            steps: list[TestStep] = []
            for step_raw in item.get("steps", []):
                if isinstance(step_raw, dict):
                    steps.append(
                        TestStep(
                            action=step_raw.get("action", "navigate"),
                            selector=step_raw.get("selector"),
                            value=step_raw.get("value"),
                            assertion=step_raw.get("assertion"),
                        )
                    )

            scenarios.append(
                TestScenario(
                    title=item.get("title", "Untitled Scenario"),
                    category=category,
                    description=item.get("description", ""),
                    preconditions=item.get("preconditions", []),
                    steps=steps,
                    expected_result=item.get("expected_result", ""),
                    tags=item.get("tags", []),
                )
            )

        return TestScenarioList(
            scenarios=scenarios,
            source_diff_summary=diff_summary,
        )
