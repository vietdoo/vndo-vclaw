"use client";

import { useRealtimeEvents } from "@/utils/useRealtimeEvents";
import { formatNumber, formatMs } from "@/utils/format";
import { Header } from "@/components/Header";
import { Panel } from "@/components/Panel";
import { MetricCard } from "@/components/MetricCard";
import { ActivityFeed } from "@/components/ActivityFeed";
import { AgentTable } from "@/components/AgentTable";
import { ToolCallLog } from "@/components/ToolCallLog";
import { LatencyChart } from "@/components/LatencyChart";
import { WorkflowDonut } from "@/components/WorkflowDonut";
import { SparkLine } from "@/components/SparkLine";

export default function DashboardPage() {
  const { metrics, activity, toolCalls, agentStats, connected, latencyHistory } =
    useRealtimeEvents();

  return (
    <div className="flex flex-col h-screen bg-[var(--bg-secondary)] overflow-hidden">
      <Header
        connected={connected}
        uptimeSeconds={metrics.uptimeSeconds}
        activeTasks={metrics.activeTasks}
      />

      <main className="flex-1 overflow-y-auto overflow-x-hidden p-5 min-h-0">
        {/* ── top metrics row ─────────────────────────────────── */}
        <div className="grid grid-cols-6 gap-3 mb-4">
          <MetricCard
            label="Total Workflows"
            value={formatNumber(metrics.totalWorkflows)}
            trendValue={`${metrics.completedWorkflows} done`}
            trend="neutral"
            mono
          >
            <SparkLine
              data={latencyHistory.map((_, i) => i)}
              width={100}
              height={24}
              color="var(--text-tertiary)"
            />
          </MetricCard>

          <MetricCard
            label="Success Rate"
            value={`${metrics.successRate}%`}
            trendValue={metrics.successRate >= 98 ? "healthy" : "degraded"}
            trend={metrics.successRate >= 98 ? "up" : "down"}
            accent={metrics.successRate >= 98}
            mono
          />

          <MetricCard
            label="Active Tasks"
            value={metrics.activeTasks}
            sub="running right now"
            mono
          />

          <MetricCard
            label="Avg Latency"
            value={formatMs(metrics.avgLatencyMs)}
            trendValue={`p99 ${formatMs(metrics.p99LatencyMs)}`}
            trend={metrics.avgLatencyMs < 500 ? "up" : "down"}
            mono
          >
            <SparkLine
              data={latencyHistory}
              width={100}
              height={24}
              color="var(--text-primary)"
            />
          </MetricCard>

          <MetricCard
            label="Agent Calls"
            value={formatNumber(metrics.totalAgentCalls)}
            sub={`${metrics.activeAgents} agents registered`}
            mono
          />

          <MetricCard
            label="Failed Workflows"
            value={metrics.failedWorkflows}
            trendValue={metrics.failedWorkflows > 0 ? `${metrics.failedWorkflows} errors` : "clean"}
            trend={metrics.failedWorkflows === 0 ? "up" : "down"}
            mono
          />
        </div>

        {/* ── middle row: charts + activity ───────────────────── */}
        <div className="grid grid-cols-12 gap-3 mb-4">
          {/* latency chart */}
          <div className="col-span-4">
            <Panel title="Latency" subtitle="30-point rolling avg">
              <LatencyChart
                data={latencyHistory}
                avg={metrics.avgLatencyMs}
                p99={metrics.p99LatencyMs}
              />
            </Panel>
          </div>

          {/* workflow donut */}
          <div className="col-span-3">
            <Panel title="Workflow Status" subtitle="all-time">
              <WorkflowDonut
                completed={metrics.completedWorkflows}
                failed={metrics.failedWorkflows}
                total={metrics.totalWorkflows}
              />
            </Panel>
          </div>

          {/* live activity feed */}
          <div className="col-span-5" style={{ minHeight: 220 }}>
            <Panel
              title="Live Events"
              badge={activity.length}
              subtitle="real-time"
              noPad
              className="h-full"
            >
              <div className="h-full overflow-y-auto" style={{ maxHeight: 220 }}>
                <ActivityFeed items={activity.slice(0, 30)} />
              </div>
            </Panel>
          </div>
        </div>

        {/* ── bottom row: agent table + tool call log ──────────── */}
        <div className="grid grid-cols-12 gap-3">
          {/* agent registry */}
          <div className="col-span-6">
            <Panel
              title="Agent Registry"
              badge={Object.keys(agentStats).length || 5}
              subtitle="registered agents"
              noPad
            >
              <AgentTable stats={agentStats} />
            </Panel>
          </div>

          {/* tool call log */}
          <div className="col-span-6">
            <Panel
              title="Tool Calls"
              badge={toolCalls.length}
              subtitle="recent"
              noPad
            >
              <ToolCallLog items={toolCalls} />
            </Panel>
          </div>
        </div>
      </main>
    </div>
  );
}
