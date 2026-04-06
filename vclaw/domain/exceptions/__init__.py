"""Platform-wide exception hierarchy."""
from __future__ import annotations


class VclawBaseError(Exception):
    """Root exception for all Vclaw platform errors."""

    def __init__(self, message: str, error_code: str = "VCLAW_ERROR") -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


class AgentNotFoundError(VclawBaseError):
    def __init__(self, capability: str) -> None:
        super().__init__(f"No agent found for capability: {capability}", "AGENT_NOT_FOUND")


class AgentExecutionError(VclawBaseError):
    def __init__(self, agent_id: str, reason: str) -> None:
        super().__init__(f"Agent {agent_id} execution failed: {reason}", "AGENT_EXEC_ERROR")


class AgentTimeoutError(VclawBaseError):
    def __init__(self, agent_id: str, timeout: int) -> None:
        super().__init__(f"Agent {agent_id} timed out after {timeout}s", "AGENT_TIMEOUT")


class IntentClassificationError(VclawBaseError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Intent classification failed: {reason}", "INTENT_CLASSIFY_ERROR")


class EventBusError(VclawBaseError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Event bus error: {reason}", "EVENT_BUS_ERROR")


class LLMProviderError(VclawBaseError):
    def __init__(self, provider: str, reason: str) -> None:
        super().__init__(f"LLM provider {provider} error: {reason}", "LLM_PROVIDER_ERROR")


class LLMAllProvidersExhaustedError(VclawBaseError):
    def __init__(self) -> None:
        super().__init__("All LLM providers exhausted", "LLM_ALL_EXHAUSTED")


class SchemaValidationError(VclawBaseError):
    def __init__(self, schema: str, reason: str) -> None:
        super().__init__(f"Schema validation failed for {schema}: {reason}", "SCHEMA_VALIDATION_ERROR")


class IdempotencyConflictError(VclawBaseError):
    def __init__(self, key: str) -> None:
        super().__init__(f"Idempotency conflict for key: {key}", "IDEMPOTENCY_CONFLICT")


class RateLimitError(VclawBaseError):
    def __init__(self, identifier: str) -> None:
        super().__init__(f"Rate limit exceeded for: {identifier}", "RATE_LIMIT_EXCEEDED")


class TelegramWebhookError(VclawBaseError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Telegram webhook error: {reason}", "TELEGRAM_WEBHOOK_ERROR")


class PluginLoadError(VclawBaseError):
    def __init__(self, plugin: str, reason: str) -> None:
        super().__init__(f"Failed to load plugin {plugin}: {reason}", "PLUGIN_LOAD_ERROR")


__all__ = [
    "VclawBaseError",
    "AgentNotFoundError",
    "AgentExecutionError",
    "AgentTimeoutError",
    "IntentClassificationError",
    "EventBusError",
    "LLMProviderError",
    "LLMAllProvidersExhaustedError",
    "SchemaValidationError",
    "IdempotencyConflictError",
    "RateLimitError",
    "TelegramWebhookError",
    "PluginLoadError",
]
