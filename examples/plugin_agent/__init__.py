"""Example external plugin agent: Weather lookup.

This demonstrates how to create a custom agent that plugs into Vclaw
without modifying any core code. Drop this folder into the `plugins/`
directory and it will be auto-discovered on startup.
"""

from examples.plugin_agent.agent import WeatherAgent
from vclaw.agents.builtin.task_management.agent import TaskManagementAgent  # noqa: just for reference

__all__ = ["WeatherAgent"]
