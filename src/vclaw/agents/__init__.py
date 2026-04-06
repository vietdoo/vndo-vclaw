"""Agent subsystem: base class, registry, plugin discovery, built-in agents."""

from vclaw.agents.base import AgentBase
from vclaw.agents.registry import AgentRegistry

__all__ = ["AgentBase", "AgentRegistry"]
