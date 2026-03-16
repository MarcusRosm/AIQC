"""
Domain exception hierarchy for the QA Platform.

All platform exceptions inherit from QABaseError so callers can catch
a broad category or be specific about what went wrong.
"""

from __future__ import annotations


class QABaseError(Exception):
    """Root exception for the QA Platform."""

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:
        if self.detail:
            return f"{self.message}\nDetail: {self.detail}"
        return self.message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r})"


class DiffAnalysisError(QABaseError):
    """Raised when the diff cannot be parsed."""


class VectorStoreError(QABaseError):
    """Raised on ChromaDB operation failures."""


class LLMError(QABaseError):
    """Raised when the LLM call fails or returns an unparsable response."""


class HealingError(QABaseError):
    """Raised during a self-healing attempt that cannot be recovered."""


class ExecutionError(QABaseError):
    """Raised when Playwright test execution fails at the platform level."""


class ConfigurationError(QABaseError):
    """Raised for missing or invalid configuration."""
