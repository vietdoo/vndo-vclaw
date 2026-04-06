# Vclaw Agent SDK Guide

## Creating a New Agent — Zero Core Changes Required

### Step 1: Copy the Template

```bash
cp -r sdk/templates/my_custom_agent vclaw/agents/my_agent
```

### Step 2: Define the Manifest

Edit `vclaw/agents/my_agent/__init__.py`. The `AgentManifest` declares everything
the registry needs:

```python
manifest: ClassVar[AgentManifest] = AgentManifest(
    name="My Agent",
    agent_id="my-agent-v1",          # Globally unique. Use kebab-case + version.
    version="1.0.0",
    description="What this agent does.",
    capabilities=[AgentCapability.TASK_MANAGEMENT],  # Maps to routing intents
    input_schema={...},              # JSON Schema for SubTask.input_data
    output_schema={...},             # JSON Schema for AgentResult.output
    tools=[...],                     # MCP tool definitions
    max_concurrent_tasks=5,          # Semaphore concurrency limit
    timeout_seconds=30,
    priority=100,                    # Lower value = higher routing priority
    requires_config=["MY_API_KEY"],  # Env vars that must be set
)
```

### Step 3: Implement `execute()`

```python
async def execute(self, subtask: SubTask) -> AgentResult:
    text = subtask.input_data["text"]
    # Your logic here
    return AgentResult(
        subtask_id=subtask.subtask_id,
        agent_id=self.manifest.agent_id,
        success=True,
        output={"message": "Done!"},
    )
```

### Step 4: Implement MCP Tools (Optional)

Define tools in `TOOLS = [ToolDefinition(...)]` and implement `call_tool()`:

```python
async def call_tool(self, tool_name: str, arguments: dict) -> dict:
    if tool_name == "my_tool":
        return await self._my_tool(arguments)
    raise NotImplementedError(f"Unknown tool: {tool_name}")
```

The orchestrator's LLM will automatically select tools based on `ToolDefinition.description`.

### Step 5: Expose `agent_class`

At the bottom of your module:

```python
agent_class = MyAgent  # Required for auto-discovery
```

### Step 6: Validate

```bash
python scripts/validate_agent.py vclaw/agents/my_agent
```

---

## Manifest Schema Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | ✅ | Human-readable display name |
| `agent_id` | `str` | ✅ | Unique ID (e.g., `my-agent-v1`) |
| `version` | `str` | ✅ | Semantic version |
| `description` | `str` | ✅ | One-line description for routing LLM |
| `capabilities` | `list[AgentCapability]` | ✅ | Routing capabilities |
| `input_schema` | `dict` | ✅ | JSON Schema for `SubTask.input_data` |
| `output_schema` | `dict` | ✅ | JSON Schema for `AgentResult.output` |
| `tools` | `list[ToolDefinition]` | ❌ | MCP-compatible tool specs |
| `max_concurrent_tasks` | `int` | ❌ | Default: 5 |
| `timeout_seconds` | `int` | ❌ | Default: 30 |
| `priority` | `int` | ❌ | Lower = higher priority. Default: 100 |
| `requires_config` | `list[str]` | ❌ | Required env var names |

---

## AgentCapability Values

```python
class AgentCapability(StrEnum):
    TASK_MANAGEMENT = "task_management"
    PUBLIC_SERVICE  = "public_service"
    CODE_REVIEW     = "code_review"
    SEARCH          = "search"
    CALENDAR        = "calendar"
    NOTIFICATION    = "notification"
    ANALYTICS       = "analytics"
    GENERAL         = "general"
```

To add a new capability: add it to the `AgentCapability` enum in
`vclaw/domain/models/base.py` and update the intent classification prompt
in `vclaw/application/orchestrator/__init__.py`.

---

## Local Debugging & Mocking

### Run agent in isolation

```python
import asyncio
from vclaw.agents.my_agent import MyAgent
from vclaw.domain.models.base import SubTask, AgentCapability

async def test_agent():
    agent = MyAgent()
    await agent.initialize()

    subtask = SubTask(
        parent_task_id="test-task-id",
        capability=AgentCapability.GENERAL,
        input_data={"text": "Test input", "entities": {}},
    )
    result = await agent.run(subtask)
    print(result.model_dump_json(indent=2))

asyncio.run(test_agent())
```

### Mock the LLM in tests

```python
from vclaw.infrastructure.llm import MockLLMProvider, LLMRouter

# MockLLMProvider returns deterministic JSON for testing
mock_router = LLMRouter(providers=[MockLLMProvider()])
agent._llm = mock_router
```

### Environment variables for dev

Create `.env`:

```
ENVIRONMENT=development
LOG_LEVEL=DEBUG
LOG_FORMAT=text
TELEGRAM_BOT_TOKEN=your_bot_token
# No LLM keys needed — MockLLMProvider activates automatically
```

---

## Registration via Python Entry Points

For packages distributed as separate PyPI packages:

```toml
# pyproject.toml
[project.entry-points."vclaw.agents"]
my-agent = "my_package.agent:agent_class"
```

After `pip install my-package`, the agent is auto-discovered on platform startup.

---

## Testing Checklist

- [ ] `agent_class` exposed at module level
- [ ] `manifest.agent_id` is globally unique
- [ ] `execute()` always returns `AgentResult` (never raises)
- [ ] `health_check()` returns `False` when dependencies unreachable
- [ ] `shutdown()` closes all open connections
- [ ] All `requires_config` env vars documented
- [ ] Input validated with Pydantic before processing
- [ ] Structured logging via `self._logger` (not `print`)
