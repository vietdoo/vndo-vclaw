"use client";

import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { Panel } from "@/components/panel";
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
  useSystemHealth,
} from "@/lib/hooks/use-realtime";
import { formatNumber, formatDuration, formatUptime } from "@/lib/utils";
import type { AgentInfo } from "@/lib/types";
import styles from "./page.module.css";

function StatChip({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className={styles.statChip}>
      <span className={styles.chipLabel}>{label}</span>
      <span className={styles.chipValue} style={color ? { color } : undefined}>{value}</span>
    </div>
  );
}

const STATUS_COLOR: Record<AgentInfo["status"], string> = {
  online: "var(--green)",
  busy: "var(--warning)",
  offline: "var(--text-tertiary)",
  degraded: "var(--error)",
};

function AgentRow({ agent }: { agent: AgentInfo }) {
  const loadPct = Math.round((agent.currentLoad / agent.maxConcurrent) * 100);
  return (
    <div className={styles.agentRow}>
      <div className={styles.agentLeft}>
        <span className={styles.agentDot} style={{ background: STATUS_COLOR[agent.status] }} />
        <div>
          <div className={styles.agentName}>{agent.name}</div>
          <div className={styles.agentMeta}>
            v{agent.version} · {agent.tasksCompleted.toLocaleString()} tasks
          </div>
        </div>
      </div>
      <div className={styles.agentRight}>
        <div className={styles.loadBar}>
          <div
            className={styles.loadFill}
            style={{
              width: `${loadPct}%`,
              background: loadPct > 80 ? "var(--error)" : loadPct > 50 ? "var(--warning)" : "var(--green)",
            }}
          />
        </div>
        <span className={styles.loadLabel}>{agent.currentLoad}/{agent.maxConcurrent}</span>
      </div>
    </div>
  );
}

function ServiceBadge({ name, status }: { name: string; status: "ok" | "error" | "degraded" }) {
  const colors = { ok: "var(--green)", error: "var(--error)", degraded: "var(--warning)" };
  return (
    <div className={styles.serviceBadge}>
      <span className={styles.serviceDot} style={{ background: colors[status] }} />
      <span className={styles.serviceName}>{name}</span>
      <span className={styles.serviceStatus} style={{ color: colors[status] }}>{status}</span>
    </div>
  );
}

export default function DashboardPage() {
  const metrics = useMetrics();
  const agents = useAgents();
  const toolCalls = useToolCallFeed(30);
  const events = useEventFeed(40);
  const timeSeries = useTimeSeries(40);
  const agentLoad = useAgentLoad(40);
  const health = useSystemHealth();

  return (
    <div className={styles.page}>
      <PageHeader
        title="Overview"
        description="Real-time platform health, throughput, and agent activity"
        live
      />

      <div className={styles.body}>
        {/* KPI row */}
        <div className={styles.kpiGrid}>
          <MetricCard
            label="Total Requests"
            value={formatNumber(metrics.totalRequests)}
            icon={<ReqIcon />}
            trend="up"
            trendValue="+12%"
          />
          <MetricCard
            label="Active Workflows"
            value={metrics.activeWorkflows}
            icon={<WfIcon />}
            color="info"
          />
          <MetricCard
            label="Avg Latency"
            value={metrics.avgLatencyMs}
            suffix="ms"
            icon={<LatIcon />}
            color="warning"
          />
          <MetricCard
            label="Success Rate"
            value={metrics.successRate.toFixed(1)}
            suffix="%"
            icon={<OkIcon />}
            color="success"
          />
          <MetricCard
            label="Tool Calls"
            value={formatNumber(metrics.totalToolCalls)}
            icon={<ToolIcon />}
          />
          <MetricCard
            label="Events / sec"
            value={metrics.eventsPerSecond}
            icon={<EvIcon />}
          />
          <MetricCard
            label="p95 Latency"
            value={metrics.p95LatencyMs}
            suffix="ms"
            icon={<LatIcon />}
            color="warning"
          />
          <MetricCard
            label="Uptime"
            value={formatUptime(metrics.uptimeSeconds)}
            icon={<UptIcon />}
            color="success"
            mono
          />
        </div>

        {/* Charts row */}
        <div className={styles.chartsRow}>
          <Panel title="Request Throughput" subtitle="req · errors / 2s">
            <ThroughputChart data={timeSeries} height={150} />
          </Panel>
          <Panel title="Latency" subtitle="p50 · p95 (ms)">
            <LatencyChart data={timeSeries} height={150} />
          </Panel>
          <Panel title="Agent Load" subtitle="concurrent tasks">
            <AgentLoadChart data={agentLoad} height={150} />
          </Panel>
        </div>

        {/* Middle row: agents + system health */}
        <div className={styles.midRow}>
          <Panel title="Agents" subtitle={`${agents.length} registered`}>
            <div className={styles.agentList}>
              {agents.map((a) => <AgentRow key={a.name} agent={a} />)}
            </div>
          </Panel>

          <Panel title="System Health">
            <div className={styles.healthGrid}>
              <StatChip label="CPU" value={`${health.cpuPercent.toFixed(0)}%`}
                color={health.cpuPercent > 80 ? "var(--error)" : health.cpuPercent > 60 ? "var(--warning)" : "var(--green)"} />
              <StatChip label="Memory" value={`${health.memoryPercent.toFixed(0)}%`}
                color={health.memoryPercent > 80 ? "var(--error)" : health.memoryPercent > 60 ? "var(--warning)" : undefined} />
              <StatChip label="Disk" value={`${health.diskPercent.toFixed(0)}%`} />
              <StatChip label="Net In" value={`${health.networkIn}KB/s`} />
              <StatChip label="Net Out" value={`${health.networkOut}KB/s`} />
              <StatChip label="Req/min" value={metrics.throughputPerMin} />
            </div>
            <div className={styles.servicesList}>
              <ServiceBadge name="PostgreSQL" status={health.services.postgres} />
              <ServiceBadge name="Redis" status={health.services.redis} />
              <ServiceBadge name="Kafka" status={health.services.kafka} />
            </div>
          </Panel>
        </div>

        {/* Bottom live feeds */}
        <div className={styles.feedsRow}>
          <Panel title="Recent Tool Calls" live noPadding>
            <div className={styles.feedScroll}>
              <ToolCallFeed calls={toolCalls} maxVisible={20} />
            </div>
          </Panel>
          <Panel title="Event Stream" live noPadding>
            <div className={styles.feedScroll}>
              <EventStream events={events} maxVisible={25} />
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function ReqIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>;
}
function WfIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="5" cy="6" r="2" /><circle cx="19" cy="6" r="2" /><circle cx="12" cy="18" r="2" /><path d="M7 6h10M5 8v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8" /><line x1="12" y1="14" x2="12" y2="16" /></svg>;
}
function LatIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>;
}
function OkIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>;
}
function ToolIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" /></svg>;
}
function EvIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" /></svg>;
}
function UptIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="2" x2="12" y2="6" /><line x1="12" y1="18" x2="12" y2="22" /><line x1="4.93" y1="4.93" x2="7.76" y2="7.76" /><line x1="16.24" y1="16.24" x2="19.07" y2="19.07" /><line x1="2" y1="12" x2="6" y2="12" /><line x1="18" y1="12" x2="22" y2="12" /></svg>;
}
