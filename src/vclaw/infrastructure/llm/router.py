"""LLM router with priority-based selection, fallback chains, and cost-aware routing."""

from __future__ import annotations

import asyncio

import structlog

from vclaw.config import LLMProviderConfig
from vclaw.domain.models import LLMRequest, LLMResponse
from vclaw.infrastructure.llm.base import LLMProvider
from vclaw.infrastructure.llm.openai_compat import OpenAICompatProvider

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class LLMRouter:
    """Provider-agnostic LLM routing layer.

    Routing strategies:
    - Priority-based: try providers in priority order (lower = higher priority)
    - Cost-optimized: route to cheapest available provider
    - Fallback chain: cascade through providers on failure

    Thread-safe via asyncio locks for provider health state.
    """

    def __init__(self, providers: list[LLMProvider] | None = None) -> None:
        self._providers: list[LLMProvider] = providers or []
        self._health: dict[str, bool] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def from_configs(cls, configs: list[LLMProviderConfig]) -> LLMRouter:
        """Factory: build router from configuration objects."""
        providers: list[LLMProvider] = []
        for cfg in sorted(configs, key=lambda c: c.priority):
            if not cfg.enabled:
                continue
            provider = OpenAICompatProvider(
                name=cfg.name,
                api_key=cfg.api_key.get_secret_value(),
                base_url=cfg.base_url or "https://api.openai.com/v1",
                model=cfg.model,
                timeout_seconds=cfg.timeout_seconds,
                cost_per_1k_input=cfg.cost_per_1k_input,
                cost_per_1k_output=cfg.cost_per_1k_output,
            )
            providers.append(provider)
        return cls(providers=providers)

    def add_provider(self, provider: LLMProvider) -> None:
        self._providers.append(provider)
        self._health[provider.name] = True

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Route request through provider fallback chain.

        Tries each provider in priority order. On failure, marks provider
        unhealthy and continues to next. Raises if all providers fail.
        """
        last_error: Exception | None = None

        for provider in self._providers:
            if not self._health.get(provider.name, True):
                logger.debug("provider_skipped_unhealthy", provider=provider.name)
                continue

            try:
                response = await provider.complete(request)
                logger.info(
                    "llm_completion",
                    provider=provider.name,
                    model=response.model,
                    latency_ms=response.latency_ms,
                    cost=response.cost_estimate,
                )
                return response
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "provider_failed",
                    provider=provider.name,
                    error=str(exc),
                )
                async with self._lock:
                    self._health[provider.name] = False

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}") from last_error

    async def health_check_all(self) -> dict[str, bool]:
        """Run health checks on all providers and update status."""
        results: dict[str, bool] = {}
        for provider in self._providers:
            healthy = await provider.health_check()
            async with self._lock:
                self._health[provider.name] = healthy
            results[provider.name] = healthy
        return results

    async def reset_provider(self, name: str) -> None:
        """Reset a provider's health status to allow retries."""
        async with self._lock:
            self._health[name] = True

    async def close(self) -> None:
        for provider in self._providers:
            try:
                await provider.close()
            except Exception:
                logger.exception("provider_close_error", provider=provider.name)
