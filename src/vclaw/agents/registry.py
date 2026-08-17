"""Agent registry: plugin discovery, lifecycle management, capability indexing."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import sys
from importlib.metadata import entry_points
from pathlib import Path

import structlog

from vclaw.agents.base import AgentBase
from vclaw.domain.events import CloudEvent, EventTypes
from vclaw.infrastructure.event_bus.base import EventBus
from vclaw.infrastructure.llm.router import LLMRouter

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class AgentRegistry:
    """Central registry for agent discovery, lifecycle, and capability lookup.

    Discovery mechanisms (in order):
    1. Python entry points (`vclaw.agents` group)
    2. Directory scanning of configured plugin directories
    3. Manual registration via `register()`

    Agents are indexed by name and capabilities for O(1) routing lookups.
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        llm_router: LLMRouter | None = None,
    ) -> None:
        self._agents: dict[str, AgentBase] = {}
        self._capability_index: dict[str, list[str]] = {}
        self._event_bus = event_bus
        self._llm_router = llm_router

    @property
    def agents(self) -> dict[str, AgentBase]:
        return dict(self._agents)

    def get(self, name: str) -> AgentBase | None:
        return self._agents.get(name)

    def find_by_capability(self, capability: str) -> list[AgentBase]:
        """Find agents that declare a given capability name."""
        agent_names = self._capability_index.get(capability, [])
        return [self._agents[n] for n in agent_names if n in self._agents]

    async def register(self, agent: AgentBase) -> None:
        """Register an agent, run its setup hook, index capabilities."""
        name = agent.name
        if name in self._agents:
            logger.warning("agent_already_registered", name=name)
            return

        if self._llm_router:
            agent._llm_router = self._llm_router

        await agent.setup()
        self._agents[name] = agent

        for cap in agent.manifest.capabilities:
            self._capability_index.setdefault(cap.name, []).append(name)

        logger.info(
            "agent_registered",
            name=name,
            capabilities=[c.name for c in agent.manifest.capabilities],
            tools=[t.name for t in agent.manifest.tools],
        )

        if self._event_bus:
            await self._event_bus.publish(
                CloudEvent(
                    type=EventTypes.AGENT_REGISTERED,
                    data={"agent_name": name, "manifest": agent.manifest.model_dump()},
                )
            )

    async def deregister(self, name: str) -> None:
        """Remove an agent from the registry and run its teardown hook."""
        agent = self._agents.pop(name, None)
        if not agent:
            return

        await agent.teardown()

        for cap_agents in self._capability_index.values():
            if name in cap_agents:
                cap_agents.remove(name)

        if self._event_bus:
            await self._event_bus.publish(
                CloudEvent(
                    type=EventTypes.AGENT_DEREGISTERED,
                    data={"agent_name": name},
                )
            )

    async def discover_entrypoints(self) -> int:
        """Load agents from `vclaw.agents` entry point group."""
        count = 0
        try:
            eps = entry_points()
            agent_eps = (
                eps.get("vclaw.agents", [])
                if isinstance(eps, dict)
                else [ep for ep in eps if ep.group == "vclaw.agents"]
            )
        except Exception:
            logger.debug("no_entrypoints_found")
            return 0

        for ep in agent_eps:
            try:
                agent_cls = ep.load()
                if inspect.isclass(agent_cls) and issubclass(agent_cls, AgentBase):
                    agent = agent_cls()
                    await self.register(agent)
                    count += 1
            except Exception:
                logger.exception("entrypoint_load_error", name=ep.name)

        logger.info("entrypoint_discovery_complete", loaded=count)
        return count

    async def discover_directories(self, directories: list[str]) -> int:
        """Scan plugin directories for agent modules with manifest definitions.

        Each directory is expected to contain Python packages with a module
        exporting a subclass of AgentBase.
        """
        count = 0
        for dir_path in directories:
            path = Path(dir_path)
            if not path.is_dir():
                logger.debug("plugin_dir_not_found", path=dir_path)
                continue

            if str(path.resolve()) not in sys.path:
                sys.path.insert(0, str(path.resolve()))

            for item in path.iterdir():
                if item.is_dir() and (item / "__init__.py").exists():
                    module_name = item.name
                elif item.is_file() and item.suffix == ".py" and item.stem != "__init__":
                    module_name = item.stem
                else:
                    continue

                try:
                    module = importlib.import_module(module_name)
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            inspect.isclass(attr)
                            and issubclass(attr, AgentBase)
                            and attr is not AgentBase
                            and hasattr(attr, "manifest")
                        ):
                            agent = attr()
                            await self.register(agent)
                            count += 1
                except Exception:
                    logger.exception("plugin_load_error", module=module_name)

        logger.info("directory_discovery_complete", loaded=count, dirs=directories)
        return count

    async def health_check_all(self) -> dict[str, bool]:
        """Run health checks on all registered agents concurrently."""

        async def _check_agent(name: str, agent: AgentBase) -> tuple[str, bool]:
            try:
                return name, await agent.health_check()
            except Exception:
                logger.exception("health_check_failed", agent=name)
                return name, False

        tasks = [_check_agent(name, agent) for name, agent in self._agents.items()]
        results_list = await asyncio.gather(*tasks)
        return dict(results_list)

    async def shutdown(self) -> None:
        """Gracefully teardown all agents."""
        for name in list(self._agents.keys()):
            await self.deregister(name)
        logger.info("registry_shutdown_complete")
