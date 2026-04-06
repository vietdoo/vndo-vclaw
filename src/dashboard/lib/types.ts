export interface PlatformMetrics {
  totalRequests: number;
  activeWorkflows: number;
  avgLatencyMs: number;
  successRate: number;
  agentCount: number;
  eventsPerSecond: number;
  uptimeSeconds: number;
  totalToolCalls: number;
  p95LatencyMs: number;
  p99LatencyMs: number;
  errorRate: number;
  throughputPerMin: number;
}

export interface AgentInfo {
  name: string;
  status: "online" | "busy" | "offline" | "degraded";
  version: string;
  capabilities: string[];
  tools: string[];
  tasksCompleted: number;
  tasksFailed: number;
  avgDurationMs: number;
  lastActiveAt: string;
  maxConcurrent: number;
  currentLoad: number;
  successRate: number;
  totalTokensUsed: number;
  description: string;
}

export interface ToolCall {
  id: string;
  agentName: string;
  toolName: string;
  status: "running" | "success" | "error" | "timeout";
  durationMs: number;
  timestamp: string;
  workflowId: string;
  parameters?: Record<string, unknown>;
  inputTokens?: number;
  outputTokens?: number;
  errorMsg?: string;
}

export interface EventEntry {
  id: string;
  type: string;
  source: string;
  timestamp: string;
  data: Record<string, unknown>;
  correlationId: string;
  tenantId?: string;
  workflowId?: string;
}

export interface LogEntry {
  id: string;
  level: "debug" | "info" | "warning" | "error" | "critical";
  message: string;
  source: string;
  timestamp: string;
  traceId?: string;
  extra?: Record<string, unknown>;
}

export interface WorkflowEvent {
  id: string;
  workflowId: string;
  eventType: string;
  status: "pending" | "running" | "completed" | "failed" | "timed_out";
  agentName?: string;
  duration?: number;
  timestamp: string;
  payload?: Record<string, unknown>;
}

export interface SystemHealth {
  cpuPercent: number;
  memoryPercent: number;
  diskPercent: number;
  networkIn: number;
  networkOut: number;
  timestamp: string;
  services: {
    postgres: "ok" | "error" | "degraded";
    redis: "ok" | "error" | "degraded";
    kafka: "ok" | "error" | "degraded";
  };
}

export interface TimeSeriesPoint {
  time: string;
  requests: number;
  latency: number;
  errors: number;
  p95?: number;
}

export interface AgentLoadPoint {
  time: string;
  [agentName: string]: string | number;
}

export interface MetricPoint {
  time: string;
  value: number;
}
