export type EventKind =
  | "workflow.started"
  | "workflow.completed"
  | "workflow.failed"
  | "agent.dispatched"
  | "agent.completed"
  | "agent.failed"
  | "tool.called"
  | "tool.returned"
  | "metrics.snapshot";

export interface DashboardEvent {
  id: string;
  kind: EventKind;
  ts: number;
  payload: Record<string, unknown>;
}

export interface MetricsSnapshot {
  totalWorkflows: number;
  completedWorkflows: number;
  failedWorkflows: number;
  totalAgentCalls: number;
  avgLatencyMs: number;
  p99LatencyMs: number;
  activeTasks: number;
  successRate: number;
  uptimeSeconds: number;
  activeAgents: number;
}

export interface ActivityItem {
  id: string;
  kind: EventKind;
  ts: number;
  label: string;
  sublabel?: string;
  meta?: string;
  status: "success" | "error" | "info" | "warning" | "pending";
}

export interface ToolCallItem {
  id: string;
  toolName: string;
  agentName: string;
  ts: number;
  durationMs?: number;
  success?: boolean;
  params?: Record<string, unknown>;
  status: "called" | "returned" | "error";
}

export interface AgentStat {
  name: string;
  calls: number;
  errors: number;
  avgDurationMs: number;
  lastSeen: number;
}
