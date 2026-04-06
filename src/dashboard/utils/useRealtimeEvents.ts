"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { DashboardEvent, MetricsSnapshot, ActivityItem, ToolCallItem, AgentStat } from "./types";

const MAX_ACTIVITY = 80;
const MAX_TOOL_CALLS = 60;

function buildActivityItem(ev: DashboardEvent): ActivityItem | null {
  const p = ev.payload;
  switch (ev.kind) {
    case "workflow.started":
      return {
        id: ev.id,
        kind: ev.kind,
        ts: ev.ts,
        label: `Workflow started`,
        sublabel: `Intent: ${p.intent as string}`,
        meta: `${p.source as string} · ${p.tenantId as string}`,
        status: "pending",
      };
    case "workflow.completed":
      return {
        id: ev.id,
        kind: ev.kind,
        ts: ev.ts,
        label: "Workflow completed",
        sublabel: `${(p.workflowId as string).slice(0, 12)}…`,
        meta: `${(p.durationMs as number).toFixed(0)} ms`,
        status: "success",
      };
    case "workflow.failed":
      return {
        id: ev.id,
        kind: ev.kind,
        ts: ev.ts,
        label: "Workflow failed",
        sublabel: p.error as string,
        meta: `${(p.durationMs as number).toFixed(0)} ms`,
        status: "error",
      };
    case "agent.dispatched":
      return {
        id: ev.id,
        kind: ev.kind,
        ts: ev.ts,
        label: `Agent dispatched`,
        sublabel: p.agentName as string,
        meta: `attempt ${p.attempt as number}`,
        status: "info",
      };
    case "agent.completed":
      return {
        id: ev.id,
        kind: ev.kind,
        ts: ev.ts,
        label: "Agent completed",
        sublabel: p.agentName as string,
        meta: `${(p.durationMs as number).toFixed(0)} ms`,
        status: "success",
      };
    case "agent.failed":
      return {
        id: ev.id,
        kind: ev.kind,
        ts: ev.ts,
        label: "Agent failed",
        sublabel: p.agentName as string,
        meta: p.error as string,
        status: "error",
      };
    default:
      return null;
  }
}

export interface RealtimeState {
  metrics: MetricsSnapshot;
  activity: ActivityItem[];
  toolCalls: ToolCallItem[];
  agentStats: Record<string, AgentStat>;
  connected: boolean;
  latencyHistory: number[];
}

const DEFAULT_METRICS: MetricsSnapshot = {
  totalWorkflows: 0,
  completedWorkflows: 0,
  failedWorkflows: 0,
  totalAgentCalls: 0,
  avgLatencyMs: 0,
  p99LatencyMs: 0,
  activeTasks: 0,
  successRate: 100,
  uptimeSeconds: 0,
  activeAgents: 0,
};

export function useRealtimeEvents(): RealtimeState {
  const [connected, setConnected] = useState(false);
  const [metrics, setMetrics] = useState<MetricsSnapshot>(DEFAULT_METRICS);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCallItem[]>([]);
  const [agentStats, setAgentStats] = useState<Record<string, AgentStat>>({});
  const [latencyHistory, setLatencyHistory] = useState<number[]>([]);

  const esRef = useRef<EventSource | null>(null);

  const handleEvent = useCallback((ev: DashboardEvent) => {
    if (ev.kind === "metrics.snapshot") {
      const snap = ev.payload as unknown as MetricsSnapshot;
      setMetrics(snap);
      setLatencyHistory((prev) => {
        const next = [...prev, snap.avgLatencyMs].slice(-30);
        return next;
      });
      return;
    }

    // activity feed
    const item = buildActivityItem(ev);
    if (item) {
      setActivity((prev) => [item, ...prev].slice(0, MAX_ACTIVITY));
    }

    // tool calls table
    if (ev.kind === "tool.called") {
      const p = ev.payload;
      const tc: ToolCallItem = {
        id: ev.id,
        toolName: p.toolName as string,
        agentName: p.agentName as string,
        ts: ev.ts,
        params: p.params as Record<string, unknown>,
        status: "called",
      };
      setToolCalls((prev) => [tc, ...prev].slice(0, MAX_TOOL_CALLS));
    }

    if (ev.kind === "tool.returned") {
      const p = ev.payload;
      setToolCalls((prev) =>
        prev.map((tc) => {
          if (tc.toolName === (p.toolName as string) && tc.status === "called") {
            return {
              ...tc,
              durationMs: p.durationMs as number,
              success: p.success as boolean,
              status: (p.success ? "returned" : "error") as "returned" | "error",
            };
          }
          return tc;
        })
      );
    }

    // agent stats
    if (ev.kind === "agent.dispatched" || ev.kind === "agent.completed" || ev.kind === "agent.failed") {
      const name = ev.payload.agentName as string;
      setAgentStats((prev) => {
        const existing = prev[name] ?? {
          name,
          calls: 0,
          errors: 0,
          avgDurationMs: 0,
          lastSeen: 0,
        };
        const updated = { ...existing, lastSeen: ev.ts };
        if (ev.kind === "agent.dispatched") updated.calls++;
        if (ev.kind === "agent.failed") updated.errors++;
        if (ev.kind === "agent.completed") {
          const dur = ev.payload.durationMs as number;
          updated.avgDurationMs =
            updated.calls > 1
              ? parseFloat(((updated.avgDurationMs + dur) / 2).toFixed(0))
              : dur;
        }
        return { ...prev, [name]: updated };
      });
    }
  }, []);

  useEffect(() => {
    const connect = () => {
      const es = new EventSource("/api/events");
      esRef.current = es;

      es.onopen = () => setConnected(true);
      es.onerror = () => {
        setConnected(false);
        es.close();
        setTimeout(connect, 3000);
      };
      es.onmessage = (e) => {
        try {
          const ev: DashboardEvent = JSON.parse(e.data);
          handleEvent(ev);
        } catch {
          // ignore malformed
        }
      };
    };

    connect();
    return () => {
      esRef.current?.close();
    };
  }, [handleEvent]);

  return { metrics, activity, toolCalls, agentStats, connected, latencyHistory };
}
