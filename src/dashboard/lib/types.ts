export interface PlatformMetrics {
  totalRequests: number;
  activeWorkflows: number;
  avgLatencyMs: number;
  p99LatencyMs: number;
  successRate: number;
  errorRate: number;
  agentCount: number;
  eventsPerSecond: number;
  uptimeSeconds: number;
  totalToolCalls: number;
  totalEvents: number;
  totalWorkflows: number;
  queueDepth: number;
  memoryUsageMb: number;
  cpuPercent: number;
  requestsPerMinute: number;
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
  p99DurationMs: number;
  lastActiveAt: string;
  maxConcurrent: number;
  currentLoad: number;
  successRate: number;
  totalRequests: number;
  createdAt: string;
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
  p99: number;
}

export interface AgentLoadPoint {
  time: string;
  [agentName: string]: string | number;
}

export interface WorkflowEntry {
  id: string;
  status: "running" | "completed" | "failed" | "queued" | "cancelled";
  agentName: string;
  intent: string;
  startedAt: string;
  completedAt: string | null;
  durationMs: number;
  steps: number;
  stepsCompleted: number;
  tenantId: string;
  source: string;
  errorMessage?: string;
}

export interface LogEntry {
  id: string;
  level: "debug" | "info" | "warn" | "error" | "fatal";
  message: string;
  source: string;
  timestamp: string;
  traceId?: string;
  metadata?: Record<string, unknown>;
}

export interface SystemStatus {
  cpu: number;
  memory: number;
  disk: number;
  networkIn: number;
  networkOut: number;
  activeConnections: number;
  redisConnected: boolean;
  kafkaConnected: boolean;
  postgresConnected: boolean;
}

export interface RequestLogEntry {
  id: string;
  method: string;
  path: string;
  status: number;
  durationMs: number;
  timestamp: string;
  source: string;
  userAgent?: string;
}
