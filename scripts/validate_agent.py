#!/usr/bin/env python3
"""
Validate an agent plugin module: checks manifest, agent_class, and interface compliance.

Usage:
    python scripts/validate_agent.py vclaw/agents/my_agent
    python scripts/validate_agent.py vclaw/agents/my_agent/__init__.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import inspect
import sys
from pathlib import Path


def load_module(path_str: str):
    path = Path(path_str)
    if path.is_dir():
        path = path / "__init__.py"
    if not path.exists():
        print(f"❌ File not found: {path}")
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("_validate_target", path)
    module = importlib.util.module_from_spec(spec)  # type: ignore
    spec.loader.exec_module(module)  # type: ignore
    return module


def validate(path_str: str) -> bool:
    print(f"\n🔍 Validating agent at: {path_str}\n")
    errors: list[str] = []
    warnings: list[str] = []

    # Add workspace root to sys.path
    workspace = Path(__file__).parent.parent
    if str(workspace) not in sys.path:
        sys.path.insert(0, str(workspace))

    module = load_module(path_str)

    # Check agent_class
    agent_class = getattr(module, "agent_class", None)
    if agent_class is None:
        errors.append("Missing `agent_class` export at module level")
    else:
        print(f"  ✅ agent_class: {agent_class.__name__}")

        # Import base class
        from vclaw.agents._base import AgentBase, AgentManifest

        if not (inspect.isclass(agent_class) and issubclass(agent_class, AgentBase)):
            errors.append(f"`agent_class` must be a subclass of AgentBase, got {agent_class}")
        else:
            print(f"  ✅ Inherits from AgentBase")

        # Check manifest
        manifest = getattr(agent_class, "manifest", None)
        if manifest is None:
            errors.append("Missing `manifest: AgentManifest` class variable")
        elif not isinstance(manifest, AgentManifest):
            errors.append(f"`manifest` must be an AgentManifest instance, got {type(manifest)}")
        else:
            print(f"  ✅ manifest: {manifest.name} ({manifest.agent_id}) v{manifest.version}")
            print(f"  ✅ capabilities: {[c.value for c in manifest.capabilities]}")
            print(f"  ✅ tools: {len(manifest.tools)}")
            print(f"  ✅ timeout: {manifest.timeout_seconds}s, priority: {manifest.priority}")

        # Check execute() signature
        if hasattr(agent_class, "execute"):
            sig = inspect.signature(agent_class.execute)
            params = list(sig.parameters.keys())
            if "subtask" not in params:
                errors.append("`execute(self, subtask: SubTask)` must have `subtask` parameter")
            else:
                print(f"  ✅ execute() signature valid")
        else:
            errors.append("Missing `execute()` method")

        # Check health_check
        if not hasattr(agent_class, "health_check"):
            warnings.append("No `health_check()` method (using default from AgentBase)")
        else:
            print(f"  ✅ health_check() present")

    # Run basic instantiation test
    if not errors and agent_class:
        async def instantiation_test():
            from vclaw.domain.models.base import AgentCapability, SubTask
            instance = agent_class()
            await instance.initialize()
            healthy = await instance.health_check()
            print(f"  ✅ Instantiation + initialize() OK")
            print(f"  ✅ health_check() = {healthy}")

            # Quick execute test
            st = SubTask(
                parent_task_id="validate-test",
                capability=instance.manifest.capabilities[0],
                input_data={"text": "test input", "entities": {}},
            )
            result = await instance.run(st)
            print(f"  ✅ execute() ran, success={result.success}")
            await instance.shutdown()

        asyncio.run(instantiation_test())

    print()
    for w in warnings:
        print(f"  ⚠️  WARNING: {w}")
    for e in errors:
        print(f"  ❌ ERROR: {e}")

    if errors:
        print(f"\n❌ Validation FAILED ({len(errors)} error(s))\n")
        return False

    print(f"\n✅ Validation PASSED\n")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/validate_agent.py <path_to_agent>")
        sys.exit(1)
    ok = validate(sys.argv[1])
    sys.exit(0 if ok else 1)
