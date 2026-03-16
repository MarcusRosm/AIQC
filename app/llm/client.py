"""
LLM Client – Ollama AsyncClient wrapper.

Provides a unified interface for text generation (streaming and non-streaming)
over the Ollama API. Always uses AsyncClient per project requirements.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import ollama

from app.core.config import get_settings
from app.core.exceptions import LLMError
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMClient:
    """
    Thin, typed wrapper around :class:`ollama.AsyncClient`.

    All methods are async and safe to call concurrently.
    Supports both streaming (for SSE forwarding) and non-streaming modes.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = ollama.AsyncClient(
            host=settings.OLLAMA_BASE_URL,
            timeout=settings.OLLAMA_TIMEOUT,
        )
        self._model = settings.OLLAMA_LLM_MODEL

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        stream: bool = False,
        options: dict[str, Any] | None = None,
    ) -> str | AsyncIterator[str]:
        """
        Call the Ollama generate endpoint.

        Args:
            prompt: The user prompt.
            system: Optional system instruction.
            stream: If ``True``, return an :class:`AsyncIterator` of text chunks.
            options: Extra Ollama model options (temperature, top_p, etc.).

        Returns:
            Either the full response string or an async iterator of chunks.

        Raises:
            :exc:`LLMError`: On API failure or empty response.
        """
        kwargs: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": stream,
            "options": options or {},
        }
        if system:
            kwargs["system"] = system

        logger.debug("LLM generate (model=%s, stream=%s, prompt_len=%d)", self._model, stream, len(prompt))

        try:
            if stream:
                return self._stream_generate(kwargs)
            response = await self._client.generate(**kwargs)
            text = response.get("response", "").strip()
            if not text:
                raise LLMError("LLM returned an empty response.")
            return text
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"Ollama generate failed: {exc}", detail=str(exc)) from exc

    async def _stream_generate(self, kwargs: dict[str, Any]) -> AsyncIterator[str]:
        """Internal generator for streaming generate."""
        try:
            async for chunk in await self._client.generate(**kwargs):
                token = chunk.get("response", "")
                if token:
                    yield token
        except Exception as exc:
            raise LLMError(f"Streaming generate failed: {exc}") from exc

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = False,
        options: dict[str, Any] | None = None,
    ) -> str | AsyncIterator[str]:
        """
        Call the Ollama chat endpoint.

        Args:
            messages: List of ``{"role": ..., "content": ...}`` dicts.
            stream: If ``True``, return an async iterator of tokens.
            options: Extra model options.

        Returns:
            Either the full assistant reply or an async iterator of tokens.
        """
        logger.debug("LLM chat (model=%s, stream=%s, msgs=%d)", self._model, stream, len(messages))
        try:
            if stream:
                return self._stream_chat(messages, options or {})
            response = await self._client.chat(
                model=self._model,
                messages=messages,
                stream=False,
                options=options or {},
            )
            text = response.message.content.strip()
            if not text:
                raise LLMError("LLM returned an empty chat response.")
            return text
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"Ollama chat failed: {exc}", detail=str(exc)) from exc

    async def _stream_chat(
        self, messages: list[dict[str, str]], options: dict[str, Any]
    ) -> AsyncIterator[str]:
        async for chunk in await self._client.chat(
            model=self._model,
            messages=messages,
            stream=True,
            options=options,
        ):
            token = chunk.message.content if chunk.message else ""
            if token:
                yield token

    async def generate_json(
        self, prompt: str, *, system: str | None = None
    ) -> dict[str, Any]:
        """
        Generate and parse a JSON response.

        Wraps :meth:`generate` with JSON extraction from the response text.

        Raises:
            :exc:`LLMError`: If the response cannot be parsed as JSON.
        """
        text = await self.generate(prompt, system=system, stream=False)
        assert isinstance(text, str)
        return self._extract_json(text)

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Extract a JSON object from the LLM response (strips markdown fences)."""
        stripped = text.strip()
        # Remove ```json ... ``` fences if present
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            stripped = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        # Find the first { ... } block
        start = stripped.find("{")
        end = stripped.rfind("}") + 1
        if start == -1 or end == 0:
            raise LLMError(
                "LLM response did not contain a JSON object.",
                detail=f"Raw: {text[:200]}",
            )
        try:
            return json.loads(stripped[start:end])
        except json.JSONDecodeError as exc:
            raise LLMError(
                f"Failed to parse LLM JSON: {exc}", detail=stripped[start:end][:300]
            ) from exc
