import type {
  PlatformMetrics,
  AgentInfo,
  ToolCall,
  EventEntry,
  TimeSeriesPoint,
  AgentLoadPoint,
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

const TOOL_NAMES = [
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
];

const EVENT_TYPES = [
  "vclaw.message.received",
  "vclaw.intent.classified",
  "vclaw.agent.dispatched",
  "vclaw.agent.completed",
  "vclaw.workflow.completed",
  "vclaw.agent.failed",
  "vclaw.task.decomposed",
  "vclaw.message.normalized",
];

const AGENT_NAMES = [
  "task_management",
  "public_service",
  "document_processor",
  "notification_hub",
];

let callCounter = 0;

export function generateMetrics(prev?: PlatformMetrics): PlatformMetrics {
  const base: PlatformMetrics = prev ?? {
    totalRequests: 14_832,
    activeWorkflows: 3,
    avgLatencyMs: 245,
    successRate: 99.2,
    agentCount: 4,
    eventsPerSecond: 42,
    uptimeSeconds: 86_400,
    totalToolCalls: 8_291,
  };

  return {
    totalRequests: base.totalRequests + randomBetween(0, 5),
    activeWorkflows: Math.max(0, base.activeWorkflows + randomBetween(-1, 2)),
    avgLatencyMs: Math.max(50, base.avgLatencyMs + randomBetween(-15, 15)),
    successRate: Math.min(100, Math.max(95, base.successRate + randomFloat(-0.3, 0.3))),
    agentCount: base.agentCount,
    eventsPerSecond: Math.max(5, base.eventsPerSecond + randomBetween(-8, 8)),
    uptimeSeconds: base.uptimeSeconds + 2,
    totalToolCalls: base.totalToolCalls + randomBetween(0, 3),
  };
}

export function generateAgents(): AgentInfo[] {
  return [
    {
      name: "task_management",
      status: "online",
      version: "0.1.0",
      capabilities: ["task_crud", "task_search", "task_analytics"],
      tools: ["search_tasks", "create_task", "update_task", "delete_task"],
      tasksCompleted: 4_120 + randomBetween(0, 10),
      tasksFailed: 23 + randomBetween(0, 1),
      avgDurationMs: 180 + randomBetween(-20, 20),
      lastActiveAt: isoNow(randomBetween(0, 5000)),
      maxConcurrent: 5,
      currentLoad: randomBetween(0, 3),
    },
    {
      name: "public_service",
      status: "online",
      version: "0.1.0",
      capabilities: ["service_info", "faq_lookup", "document_retrieval"],
      tools: ["query_service_info", "fetch_document"],
      tasksCompleted: 2_890 + randomBetween(0, 8),
      tasksFailed: 11 + randomBetween(0, 1),
      avgDurationMs: 320 + randomBetween(-30, 30),
      lastActiveAt: isoNow(randomBetween(0, 8000)),
      maxConcurrent: 5,
      currentLoad: randomBetween(0, 2),
    },
    {
      name: "document_processor",
      status: Math.random() > 0.8 ? "busy" : "online",
      version: "0.2.1",
      capabilities: ["ocr", "summarization", "entity_extraction"],
      tools: ["summarize_text", "extract_entities"],
      tasksCompleted: 1_560 + randomBetween(0, 5),
      tasksFailed: 45 + randomBetween(0, 2),
      avgDurationMs: 890 + randomBetween(-50, 50),
      lastActiveAt: isoNow(randomBetween(0, 15000)),
      maxConcurrent: 3,
      currentLoad: randomBetween(0, 3),
    },
    {
      name: "notification_hub",
      status: Math.random() > 0.95 ? "degraded" : "online",
      version: "0.1.0",
      capabilities: ["push_notification", "email", "sms"],
      tools: ["send_notification"],
      tasksCompleted: 6_240 + randomBetween(0, 12),
      tasksFailed: 8 + randomBetween(0, 1),
      avgDurationMs: 95 + randomBetween(-10, 10),
      lastActiveAt: isoNow(randomBetween(0, 3000)),
      maxConcurrent: 10,
      currentLoad: randomBetween(0, 4),
    },
  ];
}

export function generateToolCall(): ToolCall {
  callCounter++;
  const statuses: ToolCall["status"][] = ["success", "success", "success", "success", "running", "error"];
  const agentName = AGENT_NAMES[randomBetween(0, AGENT_NAMES.length - 1)];
  const toolName = TOOL_NAMES[randomBetween(0, TOOL_NAMES.length - 1)];
  const status = statuses[randomBetween(0, statuses.length - 1)];

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
  const type = EVENT_TYPES[randomBetween(0, EVENT_TYPES.length - 1)];
  return {
    id: `ev-${Date.now()}-${randomBetween(100, 999)}`,
    type,
    source: "vclaw",
    timestamp: isoNow(randomBetween(0, 1000)),
    data: { agent: AGENT_NAMES[randomBetween(0, AGENT_NAMES.length - 1)] },
    correlationId: `cor-${randomBetween(1000, 9999)}`,
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
    return {
      time,
      requests: randomBetween(20, 80),
      latency: randomBetween(100, 500),
      errors: randomBetween(0, 3),
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
      task_management: randomBetween(0, 5),
      public_service: randomBetween(0, 5),
      document_processor: randomBetween(0, 3),
      notification_hub: randomBetween(0, 10),
    };
  });
}
