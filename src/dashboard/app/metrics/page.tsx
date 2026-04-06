"use client";

import { PageHeader } from "@/components/page-header";
import { Panel } from "@/components/panel";
import { ThroughputChart } from "@/components/charts/throughput-chart";
import { LatencyChart } from "@/components/charts/latency-chart";
import { AgentLoadChart } from "@/components/charts/agent-load-chart";
import { useMetrics, useTimeSeries, useAgentLoad, useSystemHealth } from "@/lib/hooks/use-realtime";
import styles from "./page.module.css";

function HealthBar({ label, value, max = 100, warn = 60, crit = 80 }: {
  label: string;
  value: number;
  max?: number;
  warn?: number;
  crit?: number;
}) {
  const pct = Math.min((value / max) * 100, 100);
  const color = pct >= crit ? "var(--error)" : pct >= warn ? "var(--warning)" : "var(--green)";
  return (
    <div className={styles.healthRow}>
      <div className={styles.healthLabel}>
        <span className={styles.hlName}>{label}</span>
        <span className={styles.hlVal} style={{ color }}>{value.toFixed(1)}%</span>
      </div>
      <div className={styles.healthTrack}>
        <div className={styles.healthFill} style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

export default function MetricsPage() {
  const metrics = useMetrics();
  const timeSeries = useTimeSeries(60);
  const agentLoad = useAgentLoad(60);
  const health = useSystemHealth();

  const statCards = [
    { label: "Total Requests", value: metrics.totalRequests.toLocaleString(), mono: true },
    { label: "Throughput / min", value: metrics.throughputPerMin.toString(), mono: true },
    { label: "Avg Latency", value: `${metrics.avgLatencyMs}ms`, mono: true },
    { label: "p95 Latency", value: `${metrics.p95LatencyMs}ms`, mono: true },
    { label: "p99 Latency", value: `${metrics.p99LatencyMs}ms`, mono: true },
    { label: "Success Rate", value: `${metrics.successRate.toFixed(2)}%`, mono: true },
    { label: "Error Rate", value: `${metrics.errorRate.toFixed(2)}%`, mono: true },
    { label: "Events / sec", value: metrics.eventsPerSecond.toString(), mono: true },
    { label: "Tool Calls", value: metrics.totalToolCalls.toLocaleString(), mono: true },
    { label: "Active Workflows", value: metrics.activeWorkflows.toString(), mono: true },
    { label: "Agents Online", value: metrics.agentCount.toString(), mono: true },
    { label: "Uptime", value: `${(metrics.uptimeSeconds / 3600).toFixed(1)}h`, mono: true },
  ];

  return (
    <div className={styles.page}>
      <PageHeader
        title="Metrics"
        description="Platform performance metrics and resource utilization"
        live
      />

      <div className={styles.body}>
        {/* Stat grid */}
        <div className={styles.statGrid}>
          {statCards.map((s) => (
            <div key={s.label} className={styles.statCard}>
              <span className={styles.scLabel}>{s.label}</span>
              <span className={`${styles.scValue} ${s.mono ? styles.mono : ""}`}>{s.value}</span>
            </div>
          ))}
        </div>

        {/* Charts */}
        <div className={styles.chartsGrid}>
          <Panel title="Request Throughput" subtitle="requests · errors / 2s window">
            <ThroughputChart data={timeSeries} height={180} />
          </Panel>
          <Panel title="Latency Distribution" subtitle="p50 · p95 in ms">
            <LatencyChart data={timeSeries} height={180} />
          </Panel>
        </div>

        <div className={styles.chartsGrid}>
          <Panel title="Agent Concurrent Load" subtitle="tasks per agent / 2s window">
            <AgentLoadChart data={agentLoad} height={180} />
          </Panel>

          {/* System health */}
          <Panel title="System Resources">
            <div className={styles.healthBars}>
              <HealthBar label="CPU Usage" value={health.cpuPercent} />
              <HealthBar label="Memory" value={health.memoryPercent} warn={70} crit={85} />
              <HealthBar label="Disk" value={health.diskPercent} warn={70} crit={85} />
            </div>
            <div className={styles.netStats}>
              <div className={styles.netCard}>
                <span className={styles.netVal}>{health.networkIn.toLocaleString()} KB/s</span>
                <span className={styles.netLbl}>Network In</span>
              </div>
              <div className={styles.netCard}>
                <span className={styles.netVal}>{health.networkOut.toLocaleString()} KB/s</span>
                <span className={styles.netLbl}>Network Out</span>
              </div>
            </div>
            <div className={styles.services}>
              {(Object.entries(health.services) as [string, "ok" | "error" | "degraded"][]).map(([name, status]) => {
                const color = status === "ok" ? "var(--green)" : status === "degraded" ? "var(--warning)" : "var(--error)";
                return (
                  <div key={name} className={styles.svcRow}>
                    <span className={styles.svcDot} style={{ background: color }} />
                    <span className={styles.svcName}>{name}</span>
                    <span className={styles.svcStatus} style={{ color }}>{status}</span>
                  </div>
                );
              })}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
