## 2024-08-17 - asyncio.gather for Health Checks
**Learning:** Found sequential execution of health checks in `AgentRegistry.health_check_all()` and `LLMRouter.health_check_all()`. These methods wait for each agent/provider to complete health check sequentially before starting the next one.
**Action:** Optimize them by running health checks concurrently using `asyncio.gather`. This will significantly reduce the time needed to perform health checks, improving boot time or health probe latencies.
