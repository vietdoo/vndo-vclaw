"use client";

import { Header } from "@/components/header";
import { MetricCard } from "@/components/metric-card";
import { AgentList } from "@/components/agent-list";
import { ToolCallFeed } from "@/components/tool-call-feed";
import { EventStream } from "@/components/event-stream";
import { ThroughputChart } from "@/components/charts/throughput-chart";
import { LatencyChart } from "@/components/charts/latency-chart";
import { AgentLoadChart } from "@/components/charts/agent-load-chart";
import {
  useMetrics,
  useAgents,
  useToolCallFeed,
  useEventFeed,
  useTimeSeries,
  useAgentLoad,
} from "@/lib/hooks/use-realtime";
import { formatNumber } from "@/lib/utils";
import styles from "./page.module.css";

function RequestIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  );
}

function WorkflowIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83" />
    </svg>
  );
}

function LatencyIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function SuccessIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}

function AgentIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
    </svg>
  );
}

function EventIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}

function ToolIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
    </svg>
  );
}

function UptimeIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 20V10M12 20V4M6 20v-6" />
    </svg>
  );
}

export default function DashboardPage() {
  const metrics = useMetrics();
  const agents = useAgents();
  const toolCalls = useToolCallFeed();
  const events = useEventFeed();
  const timeSeries = useTimeSeries();
  const agentLoad = useAgentLoad();

  return (
    <div className={styles.root}>
      <Header uptimeSeconds={metrics.uptimeSeconds} />

      <main className={styles.main}>
        <section className={styles.metricsGrid}>
          <MetricCard
            label="Total Requests"
            value={formatNumber(metrics.totalRequests)}
            icon={<RequestIcon />}
            trend="up"
          />
          <MetricCard
            label="Active Workflows"
            value={metrics.activeWorkflows}
            icon={<WorkflowIcon />}
            color="success"
          />
          <MetricCard
            label="Avg Latency"
            value={metrics.avgLatencyMs}
            suffix="ms"
            icon={<LatencyIcon />}
            color="warning"
          />
          <MetricCard
            label="Success Rate"
            value={metrics.successRate.toFixed(1)}
            suffix="%"
            icon={<SuccessIcon />}
            color="success"
          />
          <MetricCard
            label="Agents Online"
            value={metrics.agentCount}
            icon={<AgentIcon />}
          />
          <MetricCard
            label="Events / sec"
            value={metrics.eventsPerSecond}
            icon={<EventIcon />}
          />
          <MetricCard
            label="Tool Calls"
            value={formatNumber(metrics.totalToolCalls)}
            icon={<ToolIcon />}
          />
          <MetricCard
            label="Uptime"
            value={formatNumber(metrics.uptimeSeconds)}
            suffix="s"
            icon={<UptimeIcon />}
          />
        </section>

        <section className={styles.chartsGrid}>
          <ThroughputChart data={timeSeries} />
          <LatencyChart data={timeSeries} />
          <AgentLoadChart data={agentLoad} />
        </section>

        <section className={styles.bottomGrid}>
          <div className={styles.agentPanel}>
            <AgentList agents={agents} />
          </div>
          <div className={styles.feedPanel}>
            <ToolCallFeed calls={toolCalls} />
          </div>
          <div className={styles.eventPanel}>
            <EventStream events={events} />
          </div>
        </section>
      </main>
    </div>
  );
}
