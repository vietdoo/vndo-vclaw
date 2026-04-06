"""Abstract LLM provider interface."""

from __future__ import annotations

import abc
from typing import Any

from vclaw.domain.models import LLMRequest, LLMResponse


class LLMProvider(abc.ABC):
    """Abstract base for LLM provider implementations.

    Each provider wraps a single API (OpenAI, Anthropic, OpenRouter, etc.)
    and normalizes responses into the unified LLMResponse model.
    """

    def __init__(self, name: str, api_key: str, base_url: str, model: str, **kwargs: Any) -> None:
        self.name = name
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.config = kwargs

    @abc.abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Execute a completion request."""

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is reachable."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Release resources."""
