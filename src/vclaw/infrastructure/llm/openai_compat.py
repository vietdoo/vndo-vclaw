"""OpenAI-compatible LLM provider (works with OpenAI, OpenRouter, local models)."""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from vclaw.domain.models import LLMRequest, LLMResponse
from vclaw.infrastructure.llm.base import LLMProvider

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class OpenAICompatProvider(LLMProvider):
    """Provider for any OpenAI-compatible chat completions API.

    Supports OpenAI, OpenRouter, Azure OpenAI, vLLM, Ollama, etc.
    Handles tool-calling via the standard function calling protocol.
    """

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 30.0,
        cost_per_1k_input: float = 0.0,
        cost_per_1k_output: float = 0.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(name=name, api_key=api_key, base_url=base_url, model=model, **kwargs)
        self.timeout_seconds = timeout_seconds
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self.timeout_seconds),
            )
        return self._client

    async def complete(self, request: LLMRequest) -> LLMResponse:
        client = self._get_client()
        model = request.model or self.model

        payload: dict[str, Any] = {
            "model": model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        if request.tools:
            payload["tools"] = request.tools
            payload["tool_choice"] = request.tool_choice

        if request.response_format:
            payload["response_format"] = request.response_format

        start = time.monotonic()
        try:
            resp = await client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "llm_api_error",
                provider=self.name,
                status=exc.response.status_code,
                body=exc.response.text[:500],
            )
            raise
        except httpx.TimeoutException:
            logger.error("llm_timeout", provider=self.name, model=model)
            raise

        latency_ms = (time.monotonic() - start) * 1000

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        tool_calls = []
        for tc in message.get("tool_calls", []):
            tool_calls.append(
                {
                    "id": tc.get("id", ""),
                    "type": tc.get("type", "function"),
                    "function": tc.get("function", {}),
                }
            )

        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = (input_tokens / 1000) * self.cost_per_1k_input + (
            output_tokens / 1000
        ) * self.cost_per_1k_output

        return LLMResponse(
            content=message.get("content", "") or "",
            tool_calls=tool_calls,
            model=data.get("model", model),
            provider=self.name,
            usage={
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": usage.get("total_tokens", 0),
            },
            latency_ms=latency_ms,
            cost_estimate=cost,
        )

    async def health_check(self) -> bool:
        try:
            client = self._get_client()
            resp = await client.get("/models")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
