"use client";

import { StatusBar } from "@/components/header";
import { MetricCard } from "@/components/metric-card";
import { AgentList } from "@/components/agent-list";
import { ToolCallFeed } from "@/components/tool-call-feed";
import { EventStream } from "@/components/event-stream";
import { ActivityFeed } from "@/components/activity-feed";
import { ThroughputChart } from "@/components/charts/throughput-chart";
import { LatencyChart } from "@/components/charts/latency-chart";
import { AgentLoadChart } from "@/components/charts/agent-load-chart";
import {
  useMetrics, useAgents, useToolCallFeed, useEventFeed,
  useTimeSeries, useAgentLoad, useSystemStatus, useRequestLog,
} from "@/lib/hooks/use-realtime";
import { formatNumber } from "@/lib/utils";
import {
  Activity, GitBranch, Clock, CheckCircle2, Bot, Zap,
  Wrench, ArrowUpDown, Layers, Gauge, BarChart3, AlertTriangle,
} from "lucide-react";
import styles from "./page.module.css";

export default function DashboardPage() {
  const metrics = useMetrics();
  const agents = useAgents();
  const toolCalls = useToolCallFeed();
  const events = useEventFeed();
  const timeSeries = useTimeSeries();
  const agentLoad = useAgentLoad();
  const systemStatus = useSystemStatus();
  const requestLog = useRequestLog();

  return (
    <div className={styles.root}>
      <StatusBar uptimeSeconds={metrics.uptimeSeconds} systemStatus={systemStatus} />

      <section className={styles.metricsGrid}>
        <MetricCard
          label="Total Requests"
          value={formatNumber(metrics.totalRequests)}
          subValue={`${metrics.requestsPerMinute} req/min`}
          icon={<Activity size={12} />}
          trend="up"
          trendValue="+2.4%"
          color="blue"
        />
        <MetricCard
          label="Active Workflows"
          value={metrics.activeWorkflows}
          subValue={`${formatNumber(metrics.totalWorkflows)} total`}
          icon={<GitBranch size={12} />}
          color="success"
        />
        <MetricCard
          label="Avg Latency"
          value={metrics.avgLatencyMs}
          suffix="ms"
          subValue={`p99: ${metrics.p99LatencyMs}ms`}
          icon={<Clock size={12} />}
          color="warning"
        />
        <MetricCard
          label="Success Rate"
          value={metrics.successRate.toFixed(1)}
          suffix="%"
          subValue={`${metrics.errorRate.toFixed(2)}% errors`}
          icon={<CheckCircle2 size={12} />}
          color="success"
        />
        <MetricCard
          label="Agents Online"
          value={metrics.agentCount}
          icon={<Bot size={12} />}
        />
        <MetricCard
          label="Events / sec"
          value={metrics.eventsPerSecond}
          subValue={`${formatNumber(metrics.totalEvents)} total`}
          icon={<Zap size={12} />}
          color="purple"
        />
        <MetricCard
          label="Tool Calls"
          value={formatNumber(metrics.totalToolCalls)}
          icon={<Wrench size={12} />}
        />
        <MetricCard
          label="Queue Depth"
          value={metrics.queueDepth}
          icon={<Layers size={12} />}
          color={metrics.queueDepth > 30 ? "error" : "default"}
        />
        <MetricCard
          label="CPU"
          value={metrics.cpuPercent.toFixed(0)}
          suffix="%"
          icon={<Gauge size={12} />}
          color={metrics.cpuPercent > 70 ? "warning" : "default"}
          compact
        />
        <MetricCard
          label="Memory"
          value={metrics.memoryUsageMb}
          suffix="MB"
          icon={<BarChart3 size={12} />}
          compact
        />
        <MetricCard
          label="Error Rate"
          value={metrics.errorRate.toFixed(2)}
          suffix="%"
          icon={<AlertTriangle size={12} />}
          color={metrics.errorRate > 2 ? "error" : "default"}
          compact
        />
        <MetricCard
          label="Throughput"
          value={metrics.requestsPerMinute}
          suffix="rpm"
          icon={<ArrowUpDown size={12} />}
          compact
        />
      </section>

      <section className={styles.chartsGrid}>
        <ThroughputChart data={timeSeries} />
        <LatencyChart data={timeSeries} />
        <AgentLoadChart data={agentLoad} />
      </section>

      <section className={styles.middleGrid}>
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

      <section className={styles.activitySection}>
        <ActivityFeed requests={requestLog} toolCalls={toolCalls} />
      </section>
    </div>
  );
}
