# Plugins Directory

This directory is for **drop-in agent plugins**. Any Python package placed here is automatically discovered and registered by the `AgentRegistry` at platform startup — no code changes required.

## How Auto-Discovery Works

On startup, `VclawPlatform` calls:
```python
await registry.discover_directories(settings.agent_plugin_dirs)
# settings.agent_plugin_dirs defaults to ["plugins"]
```

The registry scans this directory for Python packages (directories with `__init__.py`) and Python modules (`.py` files). It imports each one and registers any `AgentBase` subclass with a `manifest` attribute.

## Creating a Plugin Agent

### 1. Create a package directory

```
plugins/
└── my_agent/
    ├── __init__.py
    └── agent.py
```

### 2. Implement the agent

```python
# plugins/my_agent/agent.py
from __future__ import annotations

from typing import Any, ClassVar

from vclaw.agents.base import AgentBase
from vclaw.domain.models import (
    AgentCapability,
    AgentManifest,
    AgentRequest,
    AgentResponse,
)


class MyAgent(AgentBase):
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="my_agent",
        version="0.1.0",
        description="Brief description used in the orchestrator's LLM routing prompt",
        capabilities=[
            AgentCapability(
                name="my_capability",
                description="What this agent can do — be specific for accurate routing",
            ),
        ],
        max_concurrent=5,
        timeout_seconds=30.0,
    )

    async def execute(self, request: AgentRequest) -> AgentResponse:
        text = request.input_data.get("text", "")
        # ... your logic here ...
        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={"response_text": f"Processed: {text}"},
        )
```

### 3. Export from `__init__.py`

```python
# plugins/my_agent/__init__.py
from .agent import MyAgent

__all__ = ["MyAgent"]
```

### 4. Restart the platform

```bash
python -m vclaw.app
# → agent_registered name=my_agent capabilities=[my_capability]
```

---

## Plugin Examples

### Weather Agent (from `examples/plugin_agent/`)

The simplest possible example. Shows the minimum required to build an agent.

```bash
cp -r examples/plugin_agent plugins/weather
# Restart platform → WeatherAgent auto-discovered
```

### BrowserAgent as a plugin

The built-in `BrowserAgent` can also be re-used as a plugin base for domain-specific scrapers:

```python
# plugins/news_scraper/__init__.py
from .agent import NewsScraperAgent
__all__ = ["NewsScraperAgent"]

# plugins/news_scraper/agent.py
from vclaw.agents.builtin.browser.agent import BrowserAgent
from vclaw.domain.models import AgentManifest, AgentCapability, AgentRequest, AgentResponse
from typing import ClassVar

class NewsScraperAgent(BrowserAgent):
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="news_scraper",
        description="Fetches and summarizes Vietnamese news",
        capabilities=[
            AgentCapability(name="news", description="Get latest news articles"),
        ],
    )

    async def execute(self, request: AgentRequest) -> AgentResponse:
        fetch = await self._fetch_page("https://vnexpress.net")
        # ... summarize content ...
        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={"response_text": fetch["data"]["content"][:500]},
        )
```

---

## Plugin Checklist

Before deploying a plugin agent to production:

- [ ] `manifest.name` is unique across all agents
- [ ] `manifest.description` is descriptive (the orchestrator LLM reads this to route requests)
- [ ] `manifest.capabilities` have specific, non-overlapping `description` fields
- [ ] `execute()` never raises — returns `AgentResponse(success=False, error=...)` on failure
- [ ] `data["response_text"]` is set for user-facing responses
- [ ] Agent has at least one test in `tests/test_<name>_agent.py`
- [ ] Timeouts and concurrency limits are tuned for the agent's workload
- [ ] Secrets/credentials use environment variables, not hardcoded values

---

## Troubleshooting

**Agent not discovered:**
- Ensure `__init__.py` exists in the plugin directory.
- Ensure the class has a `manifest: ClassVar[AgentManifest]` attribute.
- Check logs for `plugin_load_error` entries.

**Agent registered but never routed to:**
- Check that `manifest.capabilities` descriptions are specific enough for the LLM to match.
- Try `registry.find_by_capability("your_capability")` in a test.

**Import errors:**
- All dependencies needed by the plugin must be installed in the same Python environment.
- Use `pip install -e .` to install the vclaw core package in dev mode.
