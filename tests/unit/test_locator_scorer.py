"""Unit tests – LocatorScorer (Step 6a)"""

from __future__ import annotations

import pytest

from app.healing.locator_scorer import LocatorScorer

# ── fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_DOM = """
<html>
<body>
  <form id="login-form">
    <input id="username" placeholder="Enter username" aria-label="Username" />
    <input id="password" type="password" placeholder="Password" aria-label="Password" />
    <button id="submit-btn" aria-label="Sign In" class="btn btn-primary">Sign In</button>
    <a href="/forgot" class="link">Forgot password?</a>
    <div data-testid="error-message" class="error-msg">Error</div>
  </form>
</body>
</html>
"""


@pytest.fixture
def scorer() -> LocatorScorer:
    return LocatorScorer()


# ── tests ──────────────────────────────────────────────────────────────────────

def test_score_candidates_returns_list(scorer: LocatorScorer) -> None:
    results = scorer.score_candidates("#submit-btn", SAMPLE_DOM)
    assert isinstance(results, list)


def test_score_candidates_finds_button_by_id(scorer: LocatorScorer) -> None:
    results = scorer.score_candidates("#submit-btn", SAMPLE_DOM)
    assert len(results) > 0
    top = results[0]
    assert top.confidence > 0.3


def test_score_candidates_ranked_descending(scorer: LocatorScorer) -> None:
    results = scorer.score_candidates("#submit-btn", SAMPLE_DOM)
    confidences = [r.confidence for r in results]
    assert confidences == sorted(confidences, reverse=True)


def test_score_candidates_by_aria_label(scorer: LocatorScorer) -> None:
    results = scorer.score_candidates("[aria-label='Sign In']", SAMPLE_DOM)
    assert len(results) > 0
    top = results[0]
    assert "Sign In" in top.playwright_locator


def test_score_candidates_by_testid(scorer: LocatorScorer) -> None:
    results = scorer.score_candidates("[data-testid='error-message']", SAMPLE_DOM)
    assert len(results) > 0
    top = results[0]
    assert "getByTestId" in top.playwright_locator


def test_score_candidates_has_match_reasons(scorer: LocatorScorer) -> None:
    results = scorer.score_candidates("#username", SAMPLE_DOM)
    assert len(results) > 0
    assert len(results[0].match_reasons) > 0


def test_score_candidates_top_n_limit(scorer: LocatorScorer) -> None:
    results = scorer.score_candidates("#username", SAMPLE_DOM, top_n=2)
    assert len(results) <= 2


def test_score_candidates_empty_dom_returns_empty(scorer: LocatorScorer) -> None:
    results = scorer.score_candidates("#btn", "")
    assert results == []


def test_score_candidates_confidence_in_range(scorer: LocatorScorer) -> None:
    results = scorer.score_candidates("#submit-btn", SAMPLE_DOM)
    for r in results:
        assert 0.0 <= r.confidence <= 1.0
