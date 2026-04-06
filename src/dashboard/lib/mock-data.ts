import type {
  PlatformMetrics,
  AgentInfo,
  ToolCall,
  EventEntry,
  TimeSeriesPoint,
  AgentLoadPoint,
  WorkflowEntry,
  LogEntry,
  SystemStatus,
  RequestLogEntry,
} from "./types";

function randomBetween(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function randomFloat(min: number, max: number, decimals = 1): number {
  const val = Math.random() * (max - min) + min;
  return Number(val.toFixed(decimals));
}

function isoNow(offsetMs = 0): string {
  return new Date(Date.now() - offsetMs).toISOString();
}

function pick<T>(arr: T[]): T {
  return arr[randomBetween(0, arr.length - 1)];
}

const TOOL_NAMES = [
  "search_tasks", "create_task", "update_task", "delete_task",
  "query_service_info", "fetch_document", "classify_intent",
  "summarize_text", "extract_entities", "send_notification",
  "web_search", "screenshot_page", "parse_pdf", "translate_text",
];

const EVENT_TYPES = [
  "vclaw.message.received", "vclaw.intent.classified",
  "vclaw.agent.dispatched", "vclaw.agent.completed",
  "vclaw.workflow.completed", "vclaw.agent.failed",
  "vclaw.task.decomposed", "vclaw.message.normalized",
  "vclaw.workflow.started", "vclaw.tool.called",
];

const AGENT_NAMES = [
  "task_management", "public_service",
  "document_processor", "notification_hub",
];

const INTENTS = [
  "create_task", "search_info", "send_notification",
  "process_document", "schedule_reminder", "query_faq",
  "translate_content", "analyze_data",
];

const LOG_MESSAGES = [
  "Workflow started for tenant t-1001",
  "Agent dispatched: task_management",
  "LLM request completed in 234ms",
  "Tool call: search_tasks returned 3 results",
  "Rate limit check passed for user u-4821",
  "Intent classified as create_task (confidence: 0.94)",
  "Webhook received from Telegram",
  "Redis cache hit for workflow wf-3321",
  "Event published to bus: vclaw.agent.completed",
  "Database query completed in 12ms",
  "Agent response aggregated successfully",
  "Kafka message consumed from workflow-events",
  "WebSocket connection established",
  "Health check passed - all services online",
  "Error: Agent timeout after 30000ms",
  "Warning: High memory usage detected (89%)",
];

const LOG_SOURCES = [
  "orchestrator", "agent_registry", "llm_router",
  "event_bus", "telegram_gateway", "webhook_handler",
  "rate_limiter", "state_store",
];

const HTTP_PATHS = [
  "/webhook/telegram", "/api/dashboard/metrics",
  "/api/dashboard/agents", "/api/dashboard/events",
  "/health", "/ready", "/api/v1/logs",
  "/api/v1/events", "/api/v1/stats/dashboard",
  "/ws/system", "/ws/events",
];

let callCounter = 0;

export function generateMetrics(prev?: PlatformMetrics): PlatformMetrics {
  const base: PlatformMetrics = prev ?? {
    totalRequests: 148_329,
    activeWorkflows: 7,
    avgLatencyMs: 187,
    p99LatencyMs: 890,
    successRate: 99.4,
    errorRate: 0.6,
    agentCount: 4,
    eventsPerSecond: 42,
    uptimeSeconds: 259_200,
    totalToolCalls: 82_914,
    totalEvents: 312_847,
    totalWorkflows: 24_891,
    queueDepth: 12,
    memoryUsageMb: 1_240,
    cpuPercent: 34,
    requestsPerMinute: 128,
  };

  return {
    totalRequests: base.totalRequests + randomBetween(1, 8),
    activeWorkflows: Math.max(0, Math.min(20, base.activeWorkflows + randomBetween(-2, 3))),
    avgLatencyMs: Math.max(50, base.avgLatencyMs + randomBetween(-12, 12)),
    p99LatencyMs: Math.max(200, base.p99LatencyMs + randomBetween(-30, 30)),
    successRate: Math.min(100, Math.max(95, base.successRate + randomFloat(-0.2, 0.2))),
    errorRate: Math.min(5, Math.max(0, base.errorRate + randomFloat(-0.1, 0.1))),
    agentCount: base.agentCount,
    eventsPerSecond: Math.max(5, base.eventsPerSecond + randomBetween(-6, 6)),
    uptimeSeconds: base.uptimeSeconds + 2,
    totalToolCalls: base.totalToolCalls + randomBetween(0, 5),
    totalEvents: base.totalEvents + randomBetween(2, 12),
    totalWorkflows: base.totalWorkflows + randomBetween(0, 2),
    queueDepth: Math.max(0, Math.min(50, base.queueDepth + randomBetween(-3, 3))),
    memoryUsageMb: Math.max(800, Math.min(2048, base.memoryUsageMb + randomBetween(-20, 20))),
    cpuPercent: Math.max(5, Math.min(95, base.cpuPercent + randomBetween(-5, 5))),
    requestsPerMinute: Math.max(20, base.requestsPerMinute + randomBetween(-15, 15)),
  };
}

export function generateAgents(): AgentInfo[] {
  return [
    {
      name: "task_management",
      status: "online",
      version: "1.2.0",
      capabilities: ["task_crud", "task_search", "task_analytics", "task_scheduling"],
      tools: ["search_tasks", "create_task", "update_task", "delete_task"],
      tasksCompleted: 41_203 + randomBetween(0, 10),
      tasksFailed: 234 + randomBetween(0, 2),
      avgDurationMs: 180 + randomBetween(-20, 20),
      p99DurationMs: 920 + randomBetween(-50, 50),
      lastActiveAt: isoNow(randomBetween(0, 5000)),
      maxConcurrent: 5,
      currentLoad: randomBetween(0, 3),
      successRate: 99.4,
      totalRequests: 41_437,
      createdAt: "2025-11-15T08:00:00Z",
    },
    {
      name: "public_service",
      status: "online",
      version: "1.1.0",
      capabilities: ["service_info", "faq_lookup", "document_retrieval", "knowledge_base"],
      tools: ["query_service_info", "fetch_document", "web_search"],
      tasksCompleted: 28_901 + randomBetween(0, 8),
      tasksFailed: 112 + randomBetween(0, 1),
      avgDurationMs: 320 + randomBetween(-30, 30),
      p99DurationMs: 1_400 + randomBetween(-80, 80),
      lastActiveAt: isoNow(randomBetween(0, 8000)),
      maxConcurrent: 5,
      currentLoad: randomBetween(0, 2),
      successRate: 99.6,
      totalRequests: 29_013,
      createdAt: "2025-12-01T10:00:00Z",
    },
    {
      name: "document_processor",
      status: Math.random() > 0.8 ? "busy" : "online",
      version: "2.0.3",
      capabilities: ["ocr", "summarization", "entity_extraction", "translation"],
      tools: ["summarize_text", "extract_entities", "parse_pdf", "translate_text"],
      tasksCompleted: 15_602 + randomBetween(0, 5),
      tasksFailed: 456 + randomBetween(0, 3),
      avgDurationMs: 890 + randomBetween(-50, 50),
      p99DurationMs: 4_200 + randomBetween(-200, 200),
      lastActiveAt: isoNow(randomBetween(0, 15000)),
      maxConcurrent: 3,
      currentLoad: randomBetween(0, 3),
      successRate: 97.2,
      totalRequests: 16_058,
      createdAt: "2026-01-10T14:00:00Z",
    },
    {
      name: "notification_hub",
      status: Math.random() > 0.95 ? "degraded" : "online",
      version: "1.0.1",
      capabilities: ["push_notification", "email", "sms", "webhook"],
      tools: ["send_notification"],
      tasksCompleted: 62_408 + randomBetween(0, 12),
      tasksFailed: 89 + randomBetween(0, 1),
      avgDurationMs: 95 + randomBetween(-10, 10),
      p99DurationMs: 340 + randomBetween(-30, 30),
      lastActiveAt: isoNow(randomBetween(0, 3000)),
      maxConcurrent: 10,
      currentLoad: randomBetween(0, 4),
      successRate: 99.9,
      totalRequests: 62_497,
      createdAt: "2025-10-20T09:00:00Z",
    },
  ];
}

export function generateToolCall(): ToolCall {
  callCounter++;
  const statuses: ToolCall["status"][] = ["success", "success", "success", "success", "running", "error"];
  const agentName = pick(AGENT_NAMES);
  const toolName = pick(TOOL_NAMES);
  const status = pick(statuses);

  return {
    id: `tc-${Date.now()}-${callCounter}`,
    agentName,
    toolName,
    status,
    durationMs: status === "running" ? 0 : randomBetween(12, 1200),
    timestamp: isoNow(randomBetween(0, 2000)),
    workflowId: `wf-${randomBetween(1000, 9999)}`,
  };
}

export function generateEvent(): EventEntry {
  const type = pick(EVENT_TYPES);
  return {
    id: `ev-${Date.now()}-${randomBetween(100, 999)}`,
    type,
    source: "vclaw",
    timestamp: isoNow(randomBetween(0, 1000)),
    data: { agent: pick(AGENT_NAMES) },
    correlationId: `cor-${randomBetween(1000, 9999)}`,
  };
}

export function generateTimeSeries(points = 40): TimeSeriesPoint[] {
  const now = Date.now();
  return Array.from({ length: points }, (_, i) => {
    const time = new Date(now - (points - i - 1) * 2000).toLocaleTimeString("en-US", {
      hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
    return {
      time,
      requests: randomBetween(20, 80),
      latency: randomBetween(100, 500),
      errors: randomBetween(0, 3),
      p99: randomBetween(400, 1200),
    };
  });
}

export function generateAgentLoad(points = 40): AgentLoadPoint[] {
  const now = Date.now();
  return Array.from({ length: points }, (_, i) => {
    const time = new Date(now - (points - i - 1) * 2000).toLocaleTimeString("en-US", {
      hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
    return {
      time,
      task_management: randomBetween(0, 5),
      public_service: randomBetween(0, 5),
      document_processor: randomBetween(0, 3),
      notification_hub: randomBetween(0, 10),
    };
  });
}

export function generateWorkflow(): WorkflowEntry {
  const statuses: WorkflowEntry["status"][] = ["completed", "completed", "completed", "running", "failed", "queued"];
  const status = pick(statuses);
  const steps = randomBetween(2, 6);
  const durationMs = status === "running" || status === "queued" ? 0 : randomBetween(200, 12000);

  return {
    id: `wf-${randomBetween(10000, 99999)}`,
    status,
    agentName: pick(AGENT_NAMES),
    intent: pick(INTENTS),
    startedAt: isoNow(randomBetween(0, 300000)),
    completedAt: status === "running" || status === "queued" ? null : isoNow(randomBetween(0, 60000)),
    durationMs,
    steps,
    stepsCompleted: status === "completed" ? steps : status === "failed" ? randomBetween(0, steps - 1) : randomBetween(0, steps),
    tenantId: `t-${randomBetween(1000, 1005)}`,
    source: pick(["telegram", "api", "webhook", "scheduled"]),
    errorMessage: status === "failed" ? pick(["Agent timeout", "LLM rate limit", "Invalid input", "Service unavailable"]) : undefined,
  };
}

export function generateLogEntry(): LogEntry {
  const levels: LogEntry["level"][] = ["info", "info", "info", "info", "debug", "warn", "error"];
  const level = pick(levels);
  return {
    id: `log-${Date.now()}-${randomBetween(100, 999)}`,
    level,
    message: pick(LOG_MESSAGES),
    source: pick(LOG_SOURCES),
    timestamp: isoNow(randomBetween(0, 5000)),
    traceId: Math.random() > 0.3 ? `trace-${randomBetween(10000, 99999)}` : undefined,
  };
}

export function generateSystemStatus(): SystemStatus {
  return {
    cpu: randomFloat(15, 65),
    memory: randomFloat(40, 85),
    disk: randomFloat(20, 60),
    networkIn: randomFloat(1.2, 12.5),
    networkOut: randomFloat(0.8, 8.2),
    activeConnections: randomBetween(10, 120),
    redisConnected: Math.random() > 0.02,
    kafkaConnected: Math.random() > 0.05,
    postgresConnected: Math.random() > 0.01,
  };
}

export function generateRequestLog(): RequestLogEntry {
  const methods = ["GET", "POST", "GET", "GET", "POST"];
  const statuses = [200, 200, 200, 200, 201, 204, 400, 500];
  return {
    id: `req-${Date.now()}-${randomBetween(100, 999)}`,
    method: pick(methods),
    path: pick(HTTP_PATHS),
    status: pick(statuses),
    durationMs: randomBetween(2, 800),
    timestamp: isoNow(randomBetween(0, 3000)),
    source: pick(["telegram", "api", "internal", "monitoring"]),
  };
}
