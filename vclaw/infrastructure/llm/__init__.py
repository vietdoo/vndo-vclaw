"""
LLM Abstraction Layer: provider-agnostic interface with fallback chains,
cost-aware routing, structured output enforcement via Pydantic v2.
"""
from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from typing import Any, TypeVar

import httpx
import structlog
from pydantic import BaseModel, ValidationError

from vclaw.domain.exceptions import LLMAllProvidersExhaustedError, LLMProviderError

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMMessage(BaseModel):
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None
    tool_call_id: str | None = None


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = []
    finish_reason: str = "stop"
    model: str = ""
    usage: dict[str, int] = {}
    latency_ms: float = 0.0
    provider: str = ""


class LLMProvider(ABC):
    """Abstract provider interface. Implementations: OpenRouter, Anthropic, OpenAI."""

    name: str

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Send a chat completion request and return structured response."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if provider is reachable."""


class OpenRouterProvider(LLMProvider):
    """
    OpenRouter.ai provider — acts as a gateway to many free/paid models.
    Used as the first-in-chain (cheapest) provider.
    """

    name = "openrouter"

    def __init__(self, api_key: str, base_url: str, model: str, timeout: int = 30) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "HTTP-Referer": "https://vclaw.ai",
                "X-Title": "Vclaw Platform",
            },
            timeout=timeout,
        )

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        start = time.monotonic()
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if response_format:
            payload["response_format"] = response_format

        try:
            resp = await self._client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return self._parse_response(data, time.monotonic() - start)
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                self.name, f"HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except Exception as exc:
            raise LLMProviderError(self.name, str(exc)) from exc

    def _parse_response(self, data: dict[str, Any], latency: float) -> LLMResponse:
        choice = data["choices"][0]
        message = choice["message"]
        tool_calls: list[ToolCall] = []
        for tc in message.get("tool_calls") or []:
            tool_calls.append(
                ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"]),
                )
            )
        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            model=data.get("model", self._model),
            usage=data.get("usage", {}),
            latency_ms=latency * 1000,
            provider=self.name,
        )

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get("/models", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def aclose(self) -> None:
        await self._client.aclose()


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider via native API."""

    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout: int = 30) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            base_url="https://api.anthropic.com",
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=timeout,
        )

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        start = time.monotonic()

        system_msgs = [m.content for m in messages if m.role == "system"]
        user_msgs = [m.model_dump(exclude_none=True) for m in messages if m.role != "system"]

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": user_msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_msgs:
            payload["system"] = "\n\n".join(system_msgs)
        if tools:
            anthropic_tools = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"].get("description", ""),
                    "input_schema": t["function"].get("parameters", {}),
                }
                for t in tools
            ]
            payload["tools"] = anthropic_tools

        try:
            resp = await self._client.post("/v1/messages", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return self._parse_response(data, time.monotonic() - start)
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                self.name, f"HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except Exception as exc:
            raise LLMProviderError(self.name, str(exc)) from exc

    def _parse_response(self, data: dict[str, Any], latency: float) -> LLMResponse:
        content_text: str | None = None
        tool_calls: list[ToolCall] = []
        for block in data.get("content", []):
            if block["type"] == "text":
                content_text = block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(
                    ToolCall(id=block["id"], name=block["name"], arguments=block["input"])
                )
        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            finish_reason=data.get("stop_reason", "stop"),
            model=data.get("model", self._model),
            usage=data.get("usage", {}),
            latency_ms=latency * 1000,
            provider=self.name,
        )

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get("/v1/models", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def aclose(self) -> None:
        await self._client.aclose()


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible provider (also works with any OpenAI-API-compatible endpoint)."""

    name = "openai"

    def __init__(
        self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1", timeout: int = 30
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=timeout,
        )

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        start = time.monotonic()
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if response_format:
            payload["response_format"] = response_format

        try:
            resp = await self._client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return _parse_openai_response(data, self._model, self.name, time.monotonic() - start)
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                self.name, f"HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except Exception as exc:
            raise LLMProviderError(self.name, str(exc)) from exc

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get("/models", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def aclose(self) -> None:
        await self._client.aclose()


def _parse_openai_response(
    data: dict[str, Any], model: str, provider: str, latency: float
) -> LLMResponse:
    choice = data["choices"][0]
    message = choice["message"]
    tool_calls: list[ToolCall] = []
    for tc in message.get("tool_calls") or []:
        tool_calls.append(
            ToolCall(
                id=tc["id"],
                name=tc["function"]["name"],
                arguments=json.loads(tc["function"]["arguments"]),
            )
        )
    return LLMResponse(
        content=message.get("content"),
        tool_calls=tool_calls,
        finish_reason=choice.get("finish_reason", "stop"),
        model=data.get("model", model),
        usage=data.get("usage", {}),
        latency_ms=latency * 1000,
        provider=provider,
    )


class LLMRouter:
    """
    Provider-agnostic LLM router with fallback chain and structured output validation.

    Routing strategy:
      1. Iterate providers in priority order (cost-optimized).
      2. On LLMProviderError, retry up to max_retries, then advance to next provider.
      3. If all providers exhausted → LLMAllProvidersExhaustedError.
      4. Structured output: parse LLM JSON content into target Pydantic model.
    """

    def __init__(self, providers: list[LLMProvider], max_retries_per_provider: int = 2) -> None:
        self._providers = providers
        self._max_retries = max_retries_per_provider

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        last_error: Exception | None = None
        for provider in self._providers:
            for attempt in range(1, self._max_retries + 1):
                try:
                    response = await provider.complete(
                        messages=messages,
                        tools=tools,
                        response_format=response_format,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    logger.debug(
                        "llm_request_success",
                        provider=provider.name,
                        latency_ms=round(response.latency_ms, 1),
                        attempt=attempt,
                    )
                    return response
                except LLMProviderError as exc:
                    last_error = exc
                    backoff = 2 ** attempt
                    logger.warning(
                        "llm_provider_error",
                        provider=provider.name,
                        attempt=attempt,
                        error=str(exc),
                        retry_in=backoff,
                    )
                    if attempt < self._max_retries:
                        await asyncio.sleep(backoff)

        raise LLMAllProvidersExhaustedError() from last_error

    async def complete_structured(
        self,
        messages: list[LLMMessage],
        output_model: type[T],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> T:
        """
        Request JSON-mode completion and parse into a Pydantic model.
        Raises SchemaValidationError if the LLM output fails validation.
        """
        from vclaw.domain.exceptions import SchemaValidationError

        response_format = {"type": "json_object"}
        response = await self.complete(
            messages=messages,
            tools=tools,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if not response.content:
            raise SchemaValidationError(output_model.__name__, "Empty LLM response")
        try:
            return output_model.model_validate_json(response.content)
        except (ValidationError, ValueError) as exc:
            raise SchemaValidationError(output_model.__name__, str(exc)) from exc

    @classmethod
    def from_config(cls, config: Any) -> "LLMRouter":
        """Build LLMRouter from LLMProviderConfig based on provider_priority."""
        providers: list[LLMProvider] = []
        for provider_name in config.provider_priority:
            if provider_name == "openrouter_free" and config.openrouter_api_key:
                providers.append(
                    OpenRouterProvider(
                        api_key=config.openrouter_api_key.get_secret_value(),
                        base_url=config.openrouter_base_url,
                        model=config.openrouter_free_model,
                        timeout=config.request_timeout_seconds,
                    )
                )
            elif provider_name == "anthropic" and config.anthropic_api_key:
                providers.append(
                    AnthropicProvider(
                        api_key=config.anthropic_api_key.get_secret_value(),
                        model=config.anthropic_model,
                        timeout=config.request_timeout_seconds,
                    )
                )
            elif provider_name == "openai" and config.openai_api_key:
                providers.append(
                    OpenAIProvider(
                        api_key=config.openai_api_key.get_secret_value(),
                        model=config.openai_model,
                        base_url=config.openai_base_url,
                        timeout=config.request_timeout_seconds,
                    )
                )
        if not providers:
            logger.warning("no_llm_providers_configured_using_mock")
            providers.append(MockLLMProvider())
        return cls(providers=providers, max_retries_per_provider=config.max_retries_per_provider)


class MockLLMProvider(LLMProvider):
    """
    Deterministic mock provider for local dev and testing without API keys.
    Returns intent classification or echo responses.
    """

    name = "mock"

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        if response_format and response_format.get("type") == "json_object":
            content = json.dumps({
                "primary_capability": "task_management",
                "confidence": 0.95,
                "secondary_capabilities": [],
                "extracted_entities": {"text": last_user},
                "requires_decomposition": False,
                "raw_intent": last_user,
            })
        else:
            content = f"[Mock response] Processed: {last_user[:100]}"

        return LLMResponse(
            content=content,
            tool_calls=[],
            finish_reason="stop",
            model="mock-v1",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            latency_ms=50.0,
            provider=self.name,
        )

    async def health_check(self) -> bool:
        return True
