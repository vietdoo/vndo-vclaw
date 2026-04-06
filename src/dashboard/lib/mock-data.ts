import type {
  PlatformMetrics,
  AgentInfo,
  ToolCall,
  EventEntry,
  LogEntry,
  WorkflowEvent,
  SystemHealth,
  TimeSeriesPoint,
  AgentLoadPoint,
} from "./types";

function rb(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function rf(min: number, max: number, decimals = 1): number {
  return Number((Math.random() * (max - min) + min).toFixed(decimals));
}

function isoNow(offsetMs = 0): string {
  return new Date(Date.now() - offsetMs).toISOString();
}

let counter = 0;

export const TOOL_NAMES = [
  "search_tasks",
  "create_task",
  "update_task",
  "delete_task",
  "query_service_info",
  "fetch_document",
  "classify_intent",
  "summarize_text",
  "extract_entities",
  "send_notification",
  "list_workflows",
  "get_user_context",
  "translate_text",
  "analyze_sentiment",
];

export const EVENT_TYPES = [
  "vclaw.message.received",
  "vclaw.intent.classified",
  "vclaw.agent.dispatched",
  "vclaw.agent.completed",
  "vclaw.workflow.completed",
  "vclaw.agent.failed",
  "vclaw.task.decomposed",
  "vclaw.message.normalized",
  "vclaw.agent.registered",
  "vclaw.workflow.failed",
];

export const AGENT_NAMES = [
  "task_management",
  "public_service",
  "document_processor",
  "notification_hub",
];

export const LOG_SOURCES = [
  "orchestrator",
  "agent.task_management",
  "agent.public_service",
  "agent.document_processor",
  "agent.notification_hub",
  "llm.router",
  "event.bus",
  "webhook",
];

export const LOG_MESSAGES: Record<LogEntry["level"], string[]> = {
  debug: [
    "Cache hit for intent classification",
    "Routing request to task_management agent",
    "Redis XACK: message acknowledged",
    "Semaphore acquired for agent execution",
    "Intent confidence: 0.94",
  ],
  info: [
    "Workflow completed successfully",
    "Agent dispatched: task_management",
    "Tool call succeeded: search_tasks (142ms)",
    "New connection from Telegram webhook",
    "Intent classified: task_search",
    "Event published to workflow_events channel",
  ],
  warning: [
    "Kafka producer start delayed — retrying",
    "Agent response slow: document_processor (1.2s)",
    "Redis cache miss — falling back to DB",
    "Rate limit approaching: 85/100 req/min",
    "Retry attempt 2/3 for workflow wf-4821",
  ],
  error: [
    "Agent execution failed: timeout after 60s",
    "DB connection pool exhausted",
    "LLM provider unreachable — falling back",
    "Workflow failed: max retries exceeded",
  ],
  critical: [
    "Redis connection lost — event bus degraded",
    "Orchestrator panic: unhandled exception in workflow",
  ],
};

export function generateMetrics(prev?: PlatformMetrics): PlatformMetrics {
  const base: PlatformMetrics = prev ?? {
    totalRequests: 14_832,
    activeWorkflows: 3,
    avgLatencyMs: 245,
    p95LatencyMs: 620,
    p99LatencyMs: 1100,
    successRate: 99.2,
    errorRate: 0.8,
    agentCount: 4,
    eventsPerSecond: 42,
    uptimeSeconds: 86_400,
    totalToolCalls: 8_291,
    throughputPerMin: 312,
  };

  return {
    totalRequests: base.totalRequests + rb(0, 5),
    activeWorkflows: Math.max(0, base.activeWorkflows + rb(-1, 2)),
    avgLatencyMs: Math.max(50, base.avgLatencyMs + rb(-15, 15)),
    p95LatencyMs: Math.max(200, base.p95LatencyMs + rb(-30, 30)),
    p99LatencyMs: Math.max(500, base.p99LatencyMs + rb(-50, 50)),
    successRate: Math.min(100, Math.max(95, base.successRate + rf(-0.2, 0.2))),
    errorRate: Math.min(5, Math.max(0, base.errorRate + rf(-0.1, 0.1))),
    agentCount: base.agentCount,
    eventsPerSecond: Math.max(5, base.eventsPerSecond + rb(-8, 8)),
    uptimeSeconds: base.uptimeSeconds + 2,
    totalToolCalls: base.totalToolCalls + rb(0, 3),
    throughputPerMin: Math.max(50, base.throughputPerMin + rb(-20, 20)),
  };
}

export function generateAgents(): AgentInfo[] {
  return [
    {
      name: "task_management",
      status: "online",
      version: "0.1.0",
      description: "CRUD operations and search for task entities across tenant workspaces.",
      capabilities: ["task_crud", "task_search", "task_analytics"],
      tools: ["search_tasks", "create_task", "update_task", "delete_task"],
      tasksCompleted: 4_120 + rb(0, 10),
      tasksFailed: 23 + rb(0, 1),
      avgDurationMs: 180 + rb(-20, 20),
      lastActiveAt: isoNow(rb(0, 5000)),
      maxConcurrent: 5,
      currentLoad: rb(0, 3),
      successRate: rf(98, 99.8),
      totalTokensUsed: 1_240_000 + rb(0, 5000),
    },
    {
      name: "public_service",
      status: "online",
      version: "0.1.0",
      description: "Government and public service information lookup and FAQ resolution.",
      capabilities: ["service_info", "faq_lookup", "document_retrieval"],
      tools: ["query_service_info", "fetch_document"],
      tasksCompleted: 2_890 + rb(0, 8),
      tasksFailed: 11 + rb(0, 1),
      avgDurationMs: 320 + rb(-30, 30),
      lastActiveAt: isoNow(rb(0, 8000)),
      maxConcurrent: 5,
      currentLoad: rb(0, 2),
      successRate: rf(99, 99.9),
      totalTokensUsed: 890_000 + rb(0, 3000),
    },
    {
      name: "document_processor",
      status: Math.random() > 0.8 ? "busy" : "online",
      version: "0.2.1",
      description: "OCR, text summarization, and entity extraction from uploaded documents.",
      capabilities: ["ocr", "summarization", "entity_extraction"],
      tools: ["summarize_text", "extract_entities"],
      tasksCompleted: 1_560 + rb(0, 5),
      tasksFailed: 45 + rb(0, 2),
      avgDurationMs: 890 + rb(-50, 50),
      lastActiveAt: isoNow(rb(0, 15000)),
      maxConcurrent: 3,
      currentLoad: rb(0, 3),
      successRate: rf(96, 98),
      totalTokensUsed: 3_200_000 + rb(0, 10000),
    },
    {
      name: "notification_hub",
      status: Math.random() > 0.95 ? "degraded" : "online",
      version: "0.1.0",
      description: "Multi-channel notification delivery: push, email, and SMS.",
      capabilities: ["push_notification", "email", "sms"],
      tools: ["send_notification"],
      tasksCompleted: 6_240 + rb(0, 12),
      tasksFailed: 8 + rb(0, 1),
      avgDurationMs: 95 + rb(-10, 10),
      lastActiveAt: isoNow(rb(0, 3000)),
      maxConcurrent: 10,
      currentLoad: rb(0, 4),
      successRate: rf(99.5, 99.9),
      totalTokensUsed: 320_000 + rb(0, 1000),
    },
  ];
}

export function generateToolCall(): ToolCall {
  counter++;
  const statuses: ToolCall["status"][] = ["success", "success", "success", "success", "running", "error", "timeout"];
  const agentName = AGENT_NAMES[rb(0, AGENT_NAMES.length - 1)];
  const toolName = TOOL_NAMES[rb(0, TOOL_NAMES.length - 1)];
  const status = statuses[rb(0, statuses.length - 1)];

  return {
    id: `tc-${Date.now()}-${counter}`,
    agentName,
    toolName,
    status,
    durationMs: status === "running" ? 0 : rb(12, 1400),
    timestamp: isoNow(rb(0, 2000)),
    workflowId: `wf-${rb(1000, 9999)}`,
    inputTokens: rb(50, 800),
    outputTokens: rb(20, 500),
    errorMsg: status === "error" ? "Tool execution timed out after 30s" : undefined,
  };
}

export function generateEvent(): EventEntry {
  const type = EVENT_TYPES[rb(0, EVENT_TYPES.length - 1)];
  const workflowId = `wf-${rb(1000, 9999)}`;
  return {
    id: `ev-${Date.now()}-${rb(100, 999)}`,
    type,
    source: "vclaw",
    timestamp: isoNow(rb(0, 1000)),
    data: {
      agent: AGENT_NAMES[rb(0, AGENT_NAMES.length - 1)],
      workflow_id: workflowId,
    },
    correlationId: `cor-${rb(1000, 9999)}`,
    workflowId,
    tenantId: `tenant-${rb(1, 5)}`,
  };
}

export function generateLogEntry(): LogEntry {
  const levels: LogEntry["level"][] = ["debug", "debug", "info", "info", "info", "info", "warning", "error"];
  const level = levels[rb(0, levels.length - 1)];
  const messages = LOG_MESSAGES[level];
  return {
    id: `log-${Date.now()}-${rb(100, 999)}`,
    level,
    message: messages[rb(0, messages.length - 1)],
    source: LOG_SOURCES[rb(0, LOG_SOURCES.length - 1)],
    timestamp: isoNow(rb(0, 3000)),
    traceId: `trace-${rb(10000, 99999)}`,
    extra: { pid: rb(1000, 9999) },
  };
}

export function generateWorkflowEvent(): WorkflowEvent {
  const statuses: WorkflowEvent["status"][] = [
    "completed", "completed", "completed", "running", "failed", "pending",
  ];
  const eventTypes = [
    "vclaw.workflow.completed",
    "vclaw.agent.dispatched",
    "vclaw.agent.completed",
    "vclaw.task.decomposed",
    "vclaw.workflow.failed",
  ];
  const status = statuses[rb(0, statuses.length - 1)];
  return {
    id: `wfe-${Date.now()}-${rb(100, 999)}`,
    workflowId: `wf-${rb(1000, 9999)}`,
    eventType: eventTypes[rb(0, eventTypes.length - 1)],
    status,
    agentName: AGENT_NAMES[rb(0, AGENT_NAMES.length - 1)],
    duration: status !== "pending" ? rb(50, 2000) : undefined,
    timestamp: isoNow(rb(0, 5000)),
    payload: { intent: "task_search", confidence: rf(0.8, 0.99, 2) },
  };
}

export function generateSystemHealth(): SystemHealth {
  return {
    cpuPercent: rf(5, 45),
    memoryPercent: rf(30, 65),
    diskPercent: rf(20, 55),
    networkIn: rb(100, 5000),
    networkOut: rb(50, 3000),
    timestamp: isoNow(),
    services: {
      postgres: "ok",
      redis: Math.random() > 0.05 ? "ok" : "degraded",
      kafka: Math.random() > 0.03 ? "ok" : "error",
    },
  };
}

export function generateTimeSeries(points = 30): TimeSeriesPoint[] {
  const now = Date.now();
  return Array.from({ length: points }, (_, i) => {
    const time = new Date(now - (points - i - 1) * 2000).toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    const requests = rb(20, 80);
    return {
      time,
      requests,
      latency: rb(100, 500),
      errors: rb(0, Math.ceil(requests * 0.05)),
      p95: rb(300, 800),
    };
  });
}

export function generateAgentLoad(points = 30): AgentLoadPoint[] {
  const now = Date.now();
  return Array.from({ length: points }, (_, i) => {
    const time = new Date(now - (points - i - 1) * 2000).toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    return {
      time,
      task_management: rb(0, 5),
      public_service: rb(0, 5),
      document_processor: rb(0, 3),
      notification_hub: rb(0, 10),
    };
  });
}
