"""Unit tests for LLM router and mock provider."""
from __future__ import annotations

import pytest

from vclaw.domain.exceptions import LLMAllProvidersExhaustedError, LLMProviderError
from vclaw.infrastructure.llm import (
    LLMMessage,
    LLMResponse,
    LLMRouter,
    MockLLMProvider,
)


@pytest.mark.asyncio
async def test_mock_provider_plain_completion():
    provider = MockLLMProvider()
    messages = [LLMMessage(role="user", content="Hello")]
    response = await provider.complete(messages)
    assert isinstance(response, LLMResponse)
    assert response.provider == "mock"
    assert response.content is not None


@pytest.mark.asyncio
async def test_mock_provider_json_mode():
    provider = MockLLMProvider()
    messages = [LLMMessage(role="user", content="classify this")]
    response = await provider.complete(messages, response_format={"type": "json_object"})
    import json
    data = json.loads(response.content)
    assert "primary_capability" in data
    assert "confidence" in data


@pytest.mark.asyncio
async def test_router_uses_first_provider():
    router = LLMRouter(providers=[MockLLMProvider()])
    messages = [LLMMessage(role="user", content="test")]
    response = await router.complete(messages)
    assert response.provider == "mock"


@pytest.mark.asyncio
async def test_router_fallback_on_error():
    class FailingProvider(MockLLMProvider):
        name = "failing"
        async def complete(self, *args, **kwargs):
            raise LLMProviderError("failing", "intentional failure")

    router = LLMRouter(
        providers=[FailingProvider(), MockLLMProvider()],
        max_retries_per_provider=1,
    )
    messages = [LLMMessage(role="user", content="test")]
    response = await router.complete(messages)
    assert response.provider == "mock"


@pytest.mark.asyncio
async def test_router_raises_when_all_fail():
    class FailingProvider(MockLLMProvider):
        name = "always_fail"
        async def complete(self, *args, **kwargs):
            raise LLMProviderError("always_fail", "always fails")

    router = LLMRouter(
        providers=[FailingProvider()],
        max_retries_per_provider=1,
    )
    with pytest.raises(LLMAllProvidersExhaustedError):
        await router.complete([LLMMessage(role="user", content="test")])


@pytest.mark.asyncio
async def test_complete_structured():
    from pydantic import BaseModel

    class MyOutput(BaseModel):
        primary_capability: str
        confidence: float

    router = LLMRouter(providers=[MockLLMProvider()])
    messages = [LLMMessage(role="user", content="classify")]
    result = await router.complete_structured(messages, output_model=MyOutput)
    assert isinstance(result, MyOutput)
    assert 0.0 <= result.confidence <= 1.0


@pytest.mark.asyncio
async def test_mock_health_check():
    provider = MockLLMProvider()
    assert await provider.health_check() is True
