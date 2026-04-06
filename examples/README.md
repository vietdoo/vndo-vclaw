# Examples

Reference implementations demonstrating how to build custom agents for the Vclaw platform.

## `plugin_agent/` — Weather Agent

Minimal example of a drop-in agent plugin. Demonstrates:

1. **Subclassing `AgentBase`** — The minimal contract required
2. **Declaring `AgentManifest`** — Capabilities, tools, tags
3. **Implementing `execute()`** — The core logic method
4. **Auto-discovery** — Place in `plugins/` directory for automatic registration

### Usage

```bash
# Copy to plugins/ for auto-discovery
cp -r examples/plugin_agent plugins/weather

# Or register via entry point in pyproject.toml:
# [project.entry-points."vclaw.agents"]
# weather = "plugin_agent.agent:WeatherAgent"
```

### Key Patterns Demonstrated

- `ClassVar[AgentManifest]` for static metadata
- `ToolDefinition` with typed parameters and required fields
- `AgentRequest.input_data` for accessing user input
- `AgentResponse` with `response_text` for user-facing output and structured `data`

## Creating Your Own Agent

See the [Agent SDK Guide](../README.md#6-agent-sdk-guide) in the root README for the complete guide.

**Minimal steps:**
1. Subclass `AgentBase`
2. Define `manifest: ClassVar[AgentManifest]` with name, capabilities, tools
3. Implement `async def execute(self, request: AgentRequest) -> AgentResponse`
4. Register via plugins/, entry points, or `registry.register()`
