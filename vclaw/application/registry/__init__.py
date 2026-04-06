"""
Agent Registry: dynamic discovery, capability indexing, health checks, plugin lifecycle.

Discovery strategy:
  1. Scan configured plugin directories for Python modules/packages that expose
     a module-level `manifest: AgentManifest` and a `agent_class: type[AgentBase]`.
  2. Optionally, discover via Python entry_points (group='vclaw.agents').
  3. Validate manifest schema on load; reject and log malformed plugins.
"""
from __future__ import annotations

import asyncio
import importlib
import importlib.metadata
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any

import structlog

from vclaw.agents._base import AgentBase, AgentManifest
from vclaw.domain.exceptions import AgentNotFoundError, PluginLoadError
from vclaw.domain.models.base import AgentCapability

logger = structlog.get_logger(__name__)


class AgentEntry:
    """Live registry entry for a loaded agent."""

    def __init__(self, manifest: AgentManifest, instance: AgentBase) -> None:
        self.manifest = manifest
        self.instance = instance
        self.healthy: bool = True
        self.consecutive_failures: int = 0
        self.total_tasks_handled: int = 0

    def __repr__(self) -> str:
        return f"<AgentEntry {self.manifest.agent_id} healthy={self.healthy}>"


class AgentRegistry:
    """
    Central catalog of all registered agents.

    Thread-safe via asyncio — designed for single-process async execution.
    Supports dynamic registration (plugins loaded at startup or hot-reloaded).
    """

    def __init__(self, health_check_interval: int = 30) -> None:
        self._agents: dict[str, AgentEntry] = {}
        self._capability_index: dict[AgentCapability, list[str]] = {}
        self._health_check_interval = health_check_interval
        self._health_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self._health_task = asyncio.create_task(
            self._health_check_loop(), name="agent-health-checker"
        )
        logger.info("agent_registry_started")

    async def stop(self) -> None:
        if self._health_task:
            self._health_task.cancel()
            await asyncio.gather(self._health_task, return_exceptions=True)
        for entry in self._agents.values():
            try:
                await entry.instance.shutdown()
            except Exception as exc:
                logger.warning("agent_shutdown_error", agent=entry.manifest.agent_id, error=str(exc))
        logger.info("agent_registry_stopped")

    async def register(self, agent_class: type[AgentBase]) -> None:
        """Instantiate, initialize, and register an agent class."""
        manifest = getattr(agent_class, "manifest", None)
        if not isinstance(manifest, AgentManifest):
            raise PluginLoadError(
                agent_class.__name__, "Missing or invalid `manifest: AgentManifest` class variable"
            )

        instance = agent_class()
        await instance.initialize()

        entry = AgentEntry(manifest=manifest, instance=instance)
        async with self._lock:
            self._agents[manifest.agent_id] = entry
            for cap in manifest.capabilities:
                if cap not in self._capability_index:
                    self._capability_index[cap] = []
                if manifest.agent_id not in self._capability_index[cap]:
                    self._capability_index[cap].append(manifest.agent_id)

        logger.info(
            "agent_registered",
            agent_id=manifest.agent_id,
            capabilities=[c.value for c in manifest.capabilities],
            version=manifest.version,
        )

    async def deregister(self, agent_id: str) -> None:
        async with self._lock:
            entry = self._agents.pop(agent_id, None)
            if entry:
                for agent_ids in self._capability_index.values():
                    if agent_id in agent_ids:
                        agent_ids.remove(agent_id)
                await entry.instance.shutdown()
                logger.info("agent_deregistered", agent_id=agent_id)

    def get_agent(self, agent_id: str) -> AgentBase:
        entry = self._agents.get(agent_id)
        if not entry or not entry.healthy:
            raise AgentNotFoundError(agent_id)
        return entry.instance

    def get_agents_for_capability(
        self, capability: AgentCapability
    ) -> list[AgentBase]:
        """Return all healthy agents that support the given capability, sorted by priority."""
        agent_ids = self._capability_index.get(capability, [])
        agents = [
            self._agents[aid]
            for aid in agent_ids
            if aid in self._agents and self._agents[aid].healthy
        ]
        agents.sort(key=lambda e: e.manifest.priority)
        return [e.instance for e in agents]

    def best_agent_for_capability(self, capability: AgentCapability) -> AgentBase:
        """Return the highest-priority healthy agent for a capability."""
        candidates = self.get_agents_for_capability(capability)
        if not candidates:
            raise AgentNotFoundError(capability.value)
        return candidates[0]

    def all_capabilities(self) -> dict[str, list[str]]:
        return {
            cap.value: ids for cap, ids in self._capability_index.items() if ids
        }

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {
                "agent_id": e.manifest.agent_id,
                "name": e.manifest.name,
                "version": e.manifest.version,
                "capabilities": [c.value for c in e.manifest.capabilities],
                "healthy": e.healthy,
                "total_tasks": e.total_tasks_handled,
            }
            for e in self._agents.values()
        ]

    async def _health_check_loop(self) -> None:
        while True:
            await asyncio.sleep(self._health_check_interval)
            await self._run_health_checks()

    async def _run_health_checks(self) -> None:
        for agent_id, entry in list(self._agents.items()):
            try:
                is_healthy = await asyncio.wait_for(
                    entry.instance.health_check(), timeout=5.0
                )
                if is_healthy:
                    entry.consecutive_failures = 0
                    entry.healthy = True
                else:
                    entry.consecutive_failures += 1
                    entry.healthy = entry.consecutive_failures < 3
                    logger.warning(
                        "agent_health_degraded",
                        agent_id=agent_id,
                        failures=entry.consecutive_failures,
                    )
            except Exception as exc:
                entry.consecutive_failures += 1
                entry.healthy = entry.consecutive_failures < 3
                logger.error("agent_health_check_error", agent_id=agent_id, error=str(exc))

    async def discover_and_load(self, plugin_dirs: list[str]) -> None:
        """
        Scan directories for agent modules/packages that expose `manifest` and `agent_class`.
        Also loads agents declared via Python entry_points (group='vclaw.agents').
        """
        await self._load_from_directories(plugin_dirs)
        await self._load_from_entry_points()

    async def _load_from_directories(self, plugin_dirs: list[str]) -> None:
        for dir_path_str in plugin_dirs:
            dir_path = Path(dir_path_str)
            if not dir_path.exists():
                logger.warning("plugin_dir_not_found", path=str(dir_path))
                continue

            for item in sorted(dir_path.iterdir()):
                if item.name.startswith("_"):
                    continue

                module_path: Path | None = None
                if item.is_dir() and (item / "__init__.py").exists():
                    module_path = item / "__init__.py"
                elif item.is_file() and item.suffix == ".py":
                    module_path = item

                if module_path is None:
                    continue

                await self._load_plugin_module(module_path)

    async def _load_plugin_module(self, module_path: Path) -> None:
        module_name = f"vclaw_plugin_{module_path.stem}_{id(module_path)}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                return
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)  # type: ignore[union-attr]

            agent_class = getattr(module, "agent_class", None)
            if agent_class is None or not (
                inspect.isclass(agent_class) and issubclass(agent_class, AgentBase)
            ):
                return

            await self.register(agent_class)
        except Exception as exc:
            logger.error("plugin_load_error", path=str(module_path), error=str(exc))

    async def _load_from_entry_points(self) -> None:
        try:
            eps = importlib.metadata.entry_points(group="vclaw.agents")
            for ep in eps:
                try:
                    agent_class = ep.load()
                    if inspect.isclass(agent_class) and issubclass(agent_class, AgentBase):
                        await self.register(agent_class)
                except Exception as exc:
                    logger.error("entry_point_load_error", entry_point=ep.name, error=str(exc))
        except Exception as exc:
            logger.debug("entry_points_not_available", error=str(exc))
