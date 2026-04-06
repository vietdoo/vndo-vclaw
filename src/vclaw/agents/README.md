# Agent Subsystem (`vclaw.agents`)

Pluggable agent framework with standardized execution contracts, lifecycle management, and multi-strategy discovery.

## Files

### `base.py` — `AgentBase` Abstract Class

Every agent must subclass `AgentBase` and:

1. **Declare** a `ClassVar[AgentManifest]` with capabilities, tools, concurrency limits, retry policy
2. **Implement** `async def execute(self, request: AgentRequest) -> AgentResponse`
3. **Optionally override** lifecycle hooks: `setup()`, `teardown()`, `health_check()`

**Runtime wrapping (`run()` method):**
- OpenTelemetry span creation (`agent.<name>.run`)
- Concurrency control via `asyncio.Semaphore` (from `manifest.max_concurrent`)
- Timeout enforcement via `asyncio.wait_for`
- Error isolation — exceptions are caught and returned as `AgentResponse(success=False)`
- Duration tracking in milliseconds

**Convenience methods:**
- `call_llm(request)` — Routes LLM requests through the shared `LLMRouter`
- `get_tool_schemas()` — Returns OpenAI-compatible function calling schemas from `manifest.tools`

### `registry.py` — `AgentRegistry`

Central registry for agent discovery, lifecycle, and capability-based routing.

**Discovery mechanisms (in priority order):**

1. **Entry points** (`discover_entrypoints()`) — Loads from `vclaw.agents` entry point group in `pyproject.toml`
2. **Directory scanning** (`discover_directories()`) — Scans configured plugin directories for `AgentBase` subclasses
3. **Manual** (`register()`) — Direct registration via code

**Capability index:** Maintains `dict[capability_name, list[agent_name]]` for O(1) routing lookups via `find_by_capability()`.

**Lifecycle:** `register()` calls `agent.setup()`, `deregister()` calls `agent.teardown()`. Both emit `AGENT_REGISTERED`/`AGENT_DEREGISTERED` events on the bus.

### `builtin/` — Built-in Agents

#### `task_management/` — Kanban Task Agent
- **Capabilities:** `task_management`, `task_creation`
- **Tools:** `create_task`, `update_task`, `move_task`, `list_tasks`, `get_task`, `delete_task`
- Uses LLM tool-calling for natural language → structured operations
- Keyword-based fallback when LLM is unavailable
- In-memory `TaskStore` (replace with DB for production)

#### `public_service/` — Vietnamese Government Services Agent
- **Capabilities:** `public_service`, `application_tracking`
- **Tools:** `lookup_service`, `list_services`, `submit_application`, `check_status`
- Pre-loaded service data: CCCD, Passport, Business License, Land Certificate
- Bilingual responses (Vietnamese/English)

## Creating a New Agent

```python
from vclaw.agents.base import AgentBase
from vclaw.domain.models import AgentManifest, AgentCapability, AgentRequest, AgentResponse, ToolDefinition
from typing import ClassVar

class MyAgent(AgentBase):
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="my_agent",
        version="0.1.0",
        description="What this agent does",
        capabilities=[AgentCapability(name="my_cap", description="...")],
        tools=[ToolDefinition(name="my_tool", description="...", parameters={...}, required_params=[...])],
    )

    async def execute(self, request: AgentRequest) -> AgentResponse:
        # Your logic here
        return AgentResponse(workflow_id=request.workflow_id, subtask_id=request.subtask_id, agent_name=self.name, success=True, data={...})
```

**Registration options:** Drop in `plugins/`, add entry point in `pyproject.toml`, or call `await registry.register(MyAgent())`.
