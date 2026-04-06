export interface PlatformMetrics {
  totalRequests: number;
  activeWorkflows: number;
  avgLatencyMs: number;
  successRate: number;
  agentCount: number;
  eventsPerSecond: number;
  uptimeSeconds: number;
  totalToolCalls: number;
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
}

export interface EventEntry {
  id: string;
  type: string;
  source: string;
  timestamp: string;
  data: Record<string, unknown>;
  correlationId: string;
}

export interface TimeSeriesPoint {
  time: string;
  requests: number;
  latency: number;
  errors: number;
}

export interface AgentLoadPoint {
  time: string;
  [agentName: string]: string | number;
}
