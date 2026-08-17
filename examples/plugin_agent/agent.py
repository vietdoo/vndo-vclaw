"""Example plugin agent: Weather lookup.

Demonstrates the minimal implementation required to create
a new Vclaw agent. This agent is auto-discovered when placed
in the plugins/ directory.
"""

from __future__ import annotations

from typing import ClassVar

from vclaw.agents.base import AgentBase
from vclaw.domain.models import (
    AgentCapability,
    AgentManifest,
    AgentRequest,
    AgentResponse,
    ToolDefinition,
)


class WeatherAgent(AgentBase):
    """Minimal example: a weather lookup agent.

    Step-by-step to create your own agent:
    1. Subclass AgentBase
    2. Define a ClassVar `manifest` with AgentManifest
    3. Implement `async def execute(self, request) -> AgentResponse`
    4. Place in plugins/ or register via entry points
    """

    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="weather",
        version="0.1.0",
        description="Looks up current weather for a given location.",
        capabilities=[
            AgentCapability(
                name="weather_lookup",
                description="Get current weather conditions for a city or location",
            ),
        ],
        tools=[
            ToolDefinition(
                name="get_weather",
                description="Fetch current weather for a location",
                parameters={
                    "location": {"type": "string", "description": "City name or coordinates"},
                    "units": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature unit",
                    },
                },
                required_params=["location"],
            ),
        ],
        tags=["weather", "utility"],
    )

    async def execute(self, request: AgentRequest) -> AgentResponse:
        location = request.input_data.get("location", "Hanoi")

        weather_data = {
            "location": location,
            "temperature": 28,
            "unit": "celsius",
            "condition": "Partly cloudy",
            "humidity": 75,
        }

        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={
                "response_text": (
                    f"Weather in {location}: {weather_data['temperature']}°C, "
                    f"{weather_data['condition']}, Humidity: {weather_data['humidity']}%"
                ),
                "weather": weather_data,
            },
        )
