# Agents Layer — `vclaw.agents`

This package defines the **agent execution contract**, the **registry** (plugin discovery + lifecycle), and all **built-in agents**. Third-party agents live in `plugins/` or are registered via Python entry points — both paths share the same `AgentBase` interface.

## Package Structure

```
agents/
├── base.py                     # AgentBase abstract class
├── registry.py                 # AgentRegistry: discovery + lifecycle
├── __init__.py
└── builtin/
    ├── task_management/
    │   └── agent.py            # Kanban task board agent
    └── public_service/
        └── agent.py            # Vietnamese government services agent
```

---

## `base.py` — `AgentBase`

Every agent subclasses `AgentBase`. The base class provides:

| Feature | Implementation |
|---------|---------------|
| **Manifest declaration** | `ClassVar[AgentManifest]` — static metadata for routing, discovery, and tool schemas |
| **Lifecycle hooks** | `setup()` called on registration (initializes semaphore); `teardown()` on deregistration |
| **Execution wrapper** | `run()` applies timeout, concurrency semaphore, OTel span, and structured logging around `execute()` |
| **LLM access** | `call_llm(LLMRequest)` routes through the shared `LLMRouter` |
| **Tool schemas** | `get_tool_schemas()` returns OpenAI-compatible function-calling JSON for the manifest tools |
| **Health check** | `health_check()` returns `True` by default; override for custom readiness logic |

### Execution contract

```python
class MyAgent(AgentBase):
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="my_agent",
        capabilities=[AgentCapability(name="my_cap", description="...")],
        tools=[ToolDefinition(name="my_tool", description="...", parameters={}, required_params=[])],
    )

    async def execute(self, request: AgentRequest) -> AgentResponse:
        # Core logic goes here
        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={"response_text": "..."},
        )
```

### Key invariants

- `execute()` must **never raise** — return `AgentResponse(success=False, error=...)` on failure.
- `execute()` is called inside a timeout controlled by `request.timeout_seconds` (falls back to `manifest.timeout_seconds`).
- The concurrency semaphore (`manifest.max_concurrent`, default 5) is enforced in `run()` automatically.

---

## `registry.py` — `AgentRegistry`

Central registry with three discovery mechanisms (in priority order):

### 1. Entry points (`pyproject.toml`)
```toml
[project.entry-points."vclaw.agents"]
my_agent = "my_package:MyAgent"
```
Run `discover_entrypoints()` at startup to load all registered agents.

### 2. Directory scanning
```python
await registry.discover_directories(["plugins", "my_agents_dir"])
```
Scans each directory for Python packages/modules exporting a concrete `AgentBase` subclass with a `manifest` attribute.

### 3. Manual registration
```python
await registry.register(MyAgent())
```

### Routing APIs

| Method | Signature | Use case |
|--------|-----------|----------|
| `get(name)` | `→ AgentBase | None` | Direct lookup by agent name |
| `find_by_capability(cap)` | `→ list[AgentBase]` | O(1) capability-indexed lookup |
| `health_check_all()` | `→ dict[str, bool]` | Readiness sweep across all agents |

### Events emitted

- `vclaw.agent.registered` — on successful `register()`
- `vclaw.agent.deregistered` — on `deregister()`

---

## Built-in Agents

### `TaskManagementAgent` (`builtin/task_management/agent.py`)

**Purpose:** Kanban task board operations via LLM tool-calling.

**Capabilities:** `task_management`, `task_creation`

**Tools:**

| Tool | Required params | Description |
|------|----------------|-------------|
| `create_task` | `title` | Create new task with priority, assignee, team |
| `update_task` | `task_id` | Patch any field on an existing task |
| `move_task` | `task_id`, `status` | Move between `todo → in_progress → review → done` |
| `list_tasks` | — | Filter by team, status, or assignee |
| `get_task` | `task_id` | Fetch single task details |
| `delete_task` | `task_id` | Remove task from board |

**Fallback:** Keyword-based parsing when LLM is unavailable (Vietnamese + English).

**Storage:** In-memory `TaskStore`. Replace with a DB-backed implementation for production.

---

### `PublicServiceAgent` (`builtin/public_service/agent.py`)

**Purpose:** Vietnamese government service directory — document requirements, fees, processing times, and application tracking.

**Capabilities:** `public_service`, `application_tracking`

**Tools:**

| Tool | Required params | Description |
|------|----------------|-------------|
| `lookup_service` | `service_key` | Get details for `cccd`, `passport`, `business_license`, `land_certificate` |
| `list_services` | — | List all available services |
| `submit_application` | `service_key`, `citizen_id` | Create an application record |
| `check_status` | `application_id` | Retrieve application status |

**Responses:** Bilingual (Vietnamese + English).

**Storage:** In-memory class-level dict. Production deployment should integrate with `dichvucong.gov.vn` APIs.

---

## Creating a New Agent (Step-by-Step)

### Step 1: Create the agent module

```
plugins/
└── my_agent/
    ├── __init__.py    # must export the class
    └── agent.py
```

### Step 2: Implement the class

```python
from vclaw.agents.base import AgentBase
from vclaw.domain.models import AgentCapability, AgentManifest, AgentRequest, AgentResponse
from typing import ClassVar

class MyAgent(AgentBase):
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="my_agent",
        version="0.1.0",
        description="Brief description for the orchestrator LLM prompt",
        capabilities=[
            AgentCapability(
                name="my_capability",
                description="What this agent can do — used for intent routing",
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
            data={"response_text": "Result here"},
        )
```

### Step 3: Export from `__init__.py`

```python
from .agent import MyAgent

__all__ = ["MyAgent"]
```

### Step 4: Register (choose one)

- **Auto-discovery:** Place the directory in `plugins/` → discovered at startup via `discover_directories`.
- **Entry point:** Add to `pyproject.toml` under `[project.entry-points."vclaw.agents"]` and reinstall.
- **Manual:** `await registry.register(MyAgent())` in your startup code.

---

## Testing an Agent

```python
import asyncio
from vclaw.domain.models import AgentRequest

agent = MyAgent()
asyncio.run(agent.setup())

req = AgentRequest(
    workflow_id="wf-test",
    subtask_id="st-test",
    agent_name="my_agent",
    input_data={"text": "test input"},
)
resp = asyncio.run(agent.run(req))
assert resp.success
print(resp.data)
```

See `tests/test_builtin_agents.py` and `tests/test_agent_registry.py` for full test examples.
