# Plugin Agent Example — `WeatherAgent`

This example demonstrates the **minimum required implementation** for a Vclaw plugin agent. Use it as a template when creating new agents.

## Files

```
examples/plugin_agent/
├── __init__.py        # Re-exports WeatherAgent
└── agent.py           # WeatherAgent implementation
```

## What it Shows

- Subclassing `AgentBase`
- Defining a `ClassVar[AgentManifest]` with capabilities and tool definitions
- Implementing `async def execute(request) -> AgentResponse`
- Returning structured `data` with a `response_text` key (used by `ResponseHandler` for Telegram replies)

## Quickstart

```python
import asyncio
from vclaw.domain.models import AgentRequest

from examples.plugin_agent import WeatherAgent

agent = WeatherAgent()
asyncio.run(agent.setup())

req = AgentRequest(
    workflow_id="test-wf",
    subtask_id="test-st",
    agent_name="weather",
    input_data={"location": "Ho Chi Minh City"},
)
resp = asyncio.run(agent.run(req))
print(resp.data["response_text"])
# → "Weather in Ho Chi Minh City: 28°C, Partly cloudy, Humidity: 75%"
```

## Turning this into a Real Agent

1. Replace the stubbed `weather_data` dict with a real HTTP call (e.g., `httpx.AsyncClient` against OpenWeatherMap or wttr.in).
2. Use `self.call_llm(LLMRequest(...))` if you need the LLM to parse natural language location strings.
3. Add a `RetryPolicy` to the manifest for transient HTTP errors.
4. Move the module to `plugins/weather/` to enable auto-discovery.

## Auto-discovery

Place the agent directory inside the configured plugin path (default: `plugins/`):

```
plugins/
└── weather/
    ├── __init__.py    # export WeatherAgent
    └── agent.py
```

The `AgentRegistry.discover_directories(["plugins"])` call at startup will automatically find and register the agent.
