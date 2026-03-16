"""Unit tests – ScenarioGenerator (Step 3) with mocked LLM"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.schemas import DiffResult, FileChange, TestCategory
from app.pipeline.scenario_generator import ScenarioGenerator

MOCK_LLM_RESPONSE = {
    "scenarios": [
        {
            "title": "User logs in successfully",
            "category": "happy_path",
            "description": "Verify successful login with valid credentials",
            "preconditions": ["User has a registered account"],
            "steps": [
                {"action": "navigate", "selector": None, "value": "/login", "assertion": None},
                {"action": "fill", "selector": "[aria-label='Username']", "value": "testuser", "assertion": None},
                {"action": "fill", "selector": "[aria-label='Password']", "value": "password123", "assertion": None},
                {"action": "click", "selector": "button[type='submit']", "value": None, "assertion": None},
                {"action": "assert", "selector": None, "value": None, "assertion": "URL contains /dashboard"},
            ],
            "expected_result": "User is redirected to the dashboard",
            "tags": ["auth", "login"],
        },
        {
            "title": "Login with invalid credentials",
            "category": "negative",
            "description": "Verify error is shown for wrong password",
            "preconditions": [],
            "steps": [
                {"action": "navigate", "selector": None, "value": "/login", "assertion": None},
                {"action": "fill", "selector": "[aria-label='Username']", "value": "baduser", "assertion": None},
                {"action": "fill", "selector": "[aria-label='Password']", "value": "wrong", "assertion": None},
                {"action": "click", "selector": "button[type='submit']", "value": None, "assertion": None},
                {"action": "assert", "selector": None, "value": None, "assertion": "Error message visible"},
            ],
            "expected_result": "Error message is displayed",
            "tags": ["auth", "error"],
        },
    ]
}


@pytest.fixture
def mock_diff() -> DiffResult:
    return DiffResult(
        files=[
            FileChange(
                path="app/api/routes/auth.py",
                change_type="modified",
                additions=15,
                deletions=2,
                functions_touched=["login", "logout"],
            )
        ],
        summary="Changed 1 file: auth.py",
        total_additions=15,
        total_deletions=2,
    )


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.generate_json = AsyncMock(return_value=MOCK_LLM_RESPONSE)
    return llm


@pytest.mark.asyncio
async def test_generate_returns_scenario_list(mock_llm, mock_diff: DiffResult) -> None:
    gen = ScenarioGenerator(llm=mock_llm)
    result = await gen.generate(mock_diff, context=[])
    assert result is not None
    assert len(result.scenarios) == 2


@pytest.mark.asyncio
async def test_generate_scenario_categories(mock_llm, mock_diff: DiffResult) -> None:
    gen = ScenarioGenerator(llm=mock_llm)
    result = await gen.generate(mock_diff, context=[])
    cats = {s.category for s in result.scenarios}
    assert TestCategory.HAPPY_PATH in cats
    assert TestCategory.NEGATIVE in cats


@pytest.mark.asyncio
async def test_generate_scenario_has_steps(mock_llm, mock_diff: DiffResult) -> None:
    gen = ScenarioGenerator(llm=mock_llm)
    result = await gen.generate(mock_diff, context=[])
    for scenario in result.scenarios:
        assert len(scenario.steps) > 0


@pytest.mark.asyncio
async def test_generate_diff_summary_stored(mock_llm, mock_diff: DiffResult) -> None:
    gen = ScenarioGenerator(llm=mock_llm)
    result = await gen.generate(mock_diff, context=[])
    assert result.source_diff_summary == mock_diff.summary


@pytest.mark.asyncio
async def test_generate_retries_on_llm_error(mock_diff: DiffResult) -> None:
    from app.core.exceptions import LLMError
    llm = MagicMock()
    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise LLMError("temp failure")
        return MOCK_LLM_RESPONSE

    llm.generate_json = side_effect
    gen = ScenarioGenerator(llm=llm)
    result = await gen.generate(mock_diff, context=[])
    assert len(result.scenarios) == 2
    assert call_count == 2
