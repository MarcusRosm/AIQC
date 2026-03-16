"""
Step 6b – Self-Healing Engine.

Orchestrates the full self-healing flow:
  1. Score DOM candidates with LocatorScorer (heuristic, fast)
  2. If <threshold, call LLM for AI-assisted healing suggestion
  3. Build a PR-comment summary with old/new selector and confidence score
"""

from __future__ import annotations

from textwrap import dedent

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.schemas import (
    ExecutionResult,
    HealCandidate,
    HealResult,
    HealStatus,
    TestStatus,
)
from app.healing.locator_scorer import LocatorScorer
from app.llm.client import LLMClient
from app.llm.prompts import SYSTEM_HEALER, self_heal_prompt

logger = get_logger(__name__)


class SelfHealingEngine:
    """
    Step 6: Attempts to auto-repair broken Playwright locators.

    Two-tier healing strategy:
    1. **Heuristic** – LocatorScorer scores DOM candidates immediately.
    2. **AI-assist** – LLM called when heuristic confidence < threshold.

    On success it generates a PR comment suggestion; on failure it
    escalates to ``hard_failure`` for human review.
    """

    def __init__(
        self,
        scorer: LocatorScorer | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self._scorer = scorer or LocatorScorer()
        self._llm = llm or LLMClient()
        self._settings = get_settings()

    async def heal(self, failure: ExecutionResult) -> HealResult:
        """
        Attempt to heal a failed test's broken locator.

        Args:
            failure: The failed :class:`ExecutionResult` with a non-None
                     ``failing_selector`` and optional ``dom_snapshot``.

        Returns:
            A :class:`HealResult` with status, candidates, and PR comment.
        """
        selector = failure.failing_selector
        dom = failure.dom_snapshot or ""

        if not selector:
            logger.info("No failing selector on result '%s' – skipping heal.", failure.test_title)
            return HealResult(
                original_selector="",
                status=HealStatus.SKIPPED,
                test_title=failure.test_title,
            )

        logger.info("Healing broken selector '%s' for '%s'", selector, failure.test_title)

        # Tier 1: heuristic scoring
        candidates = self._scorer.score_candidates(selector, dom)
        top = candidates[0] if candidates else None

        # Tier 2: LLM if heuristic confidence is low or no candidates found
        threshold = self._settings.HEAL_CONFIDENCE_THRESHOLD
        if (not top or top.confidence < threshold) and dom:
            logger.info(
                "Heuristic confidence %.2f < threshold %.2f – calling LLM.",
                top.confidence if top else 0.0,
                threshold,
            )
            llm_candidates = await self._llm_heal(selector, dom, failure.test_title)
            # Merge and re-rank
            all_candidates = llm_candidates + candidates
            all_candidates.sort(key=lambda c: c.confidence, reverse=True)
            candidates = all_candidates
            top = candidates[0] if candidates else None

        if not top or top.confidence < 0.3:
            logger.error(
                "Self-healing failed for '%s' – no confident candidate found.", failure.test_title
            )
            return HealResult(
                original_selector=selector,
                status=HealStatus.HARD_FAILURE,
                all_candidates=candidates,
                test_title=failure.test_title,
            )

        pr_comment = self._build_pr_comment(failure.test_title, selector, top)
        logger.info(
            "Healing SUCCESS for '%s': confidence=%.2f selector='%s'",
            failure.test_title,
            top.confidence,
            top.playwright_locator,
        )
        return HealResult(
            original_selector=selector,
            status=HealStatus.SUCCESS,
            chosen_candidate=top,
            all_candidates=candidates,
            pr_comment=pr_comment,
            test_title=failure.test_title,
        )

    async def _llm_heal(
        self,
        selector: str,
        dom: str,
        test_title: str,
    ) -> list[HealCandidate]:
        """Ask the LLM for healing suggestions."""
        prompt = self_heal_prompt(selector, dom, test_title)
        try:
            raw = await self._llm.generate_json(prompt, system=SYSTEM_HEALER)
            candidates_raw = raw.get("candidates", [])
            result: list[HealCandidate] = []
            for item in candidates_raw:
                if not isinstance(item, dict):
                    continue
                result.append(
                    HealCandidate(
                        selector=item.get("selector", selector),
                        playwright_locator=item.get("playwright_locator", ""),
                        confidence=float(item.get("confidence", 0.5)),
                        match_reasons=item.get("match_reasons", ["LLM suggestion"]),
                    )
                )
            return result
        except Exception as exc:
            logger.warning("LLM heal suggestion failed: %s", exc)
            return []

    @staticmethod
    def _build_pr_comment(title: str, old_sel: str, candidate: HealCandidate) -> str:
        reasons_md = "\n".join(f"  - {r}" for r in candidate.match_reasons)
        return dedent(f"""
            ### 🔧 Self-Healing Suggestion

            **Test:** `{title}`
            **Confidence:** `{candidate.confidence * 100:.1f}%`

            #### Before (broken selector)
            ```
            {old_sel}
            ```

            #### After (suggested fix)
            ```typescript
            {candidate.playwright_locator}
            ```

            #### Match reasons
            {reasons_md or "  - Heuristic similarity match"}

            > *Auto-generated by the AI-Driven QA Platform self-healing engine.*
        """).strip()
