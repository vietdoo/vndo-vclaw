"use client";

import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Panel } from "@/components/panel";
import { useAgents, useMetrics } from "@/lib/hooks/use-realtime";
import { formatDuration, formatNumber, relativeTime } from "@/lib/utils";
import type { AgentInfo } from "@/lib/types";
import styles from "./page.module.css";

const STATUS_LABELS: Record<AgentInfo["status"], string> = {
  online: "Healthy",
  busy: "Busy",
  offline: "Offline",
  degraded: "Degraded",
};

const AGENT_COLORS: Record<string, string> = {
  task_management: "#0070f3",
  public_service: "#3dd68c",
  document_processor: "#8b5cf6",
  notification_hub: "#f5a623",
};

function AgentDetailCard({ agent }: { agent: AgentInfo }) {
  const loadPct = Math.round((agent.currentLoad / agent.maxConcurrent) * 100);
  const color = AGENT_COLORS[agent.name] ?? "#888";

  return (
    <div className={styles.agentCard}>
      <div className={styles.cardHeader}>
        <div className={styles.agentIdent}>
          <div className={styles.agentAvatar} style={{ background: `${color}20`, borderColor: `${color}40` }}>
            <span style={{ color }}>{agent.name.charAt(0).toUpperCase()}</span>
          </div>
          <div>
            <div className={styles.agentNameRow}>
              <span className={styles.agentName}>{agent.name}</span>
              <span className={styles.agentVersion}>v{agent.version}</span>
            </div>
            <p className={styles.agentDesc}>{agent.description}</p>
          </div>
        </div>
        <span className={styles.statusBadge} data-status={agent.status}>
          {STATUS_LABELS[agent.status]}
        </span>
      </div>

      <div className={styles.statsGrid}>
        <div className={styles.stat}>
          <span className={styles.statVal}>{formatNumber(agent.tasksCompleted)}</span>
          <span className={styles.statLbl}>Completed</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statVal} data-error={agent.tasksFailed > 10 ? "true" : "false"}>
            {agent.tasksFailed}
          </span>
          <span className={styles.statLbl}>Failed</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statVal}>{formatDuration(agent.avgDurationMs)}</span>
          <span className={styles.statLbl}>Avg Duration</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statVal}>{agent.successRate.toFixed(1)}%</span>
          <span className={styles.statLbl}>Success Rate</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statVal}>{formatNumber(agent.totalTokensUsed)}</span>
          <span className={styles.statLbl}>Tokens Used</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statVal}>{agent.maxConcurrent}</span>
          <span className={styles.statLbl}>Max Concurrent</span>
        </div>
      </div>

      <div className={styles.loadSection}>
        <div className={styles.loadHeader}>
          <span className={styles.loadTitle}>Current Load</span>
          <span className={styles.loadCount}>{agent.currentLoad} / {agent.maxConcurrent}</span>
        </div>
        <div className={styles.loadTrack}>
          <div
            className={styles.loadFill}
            style={{
              width: `${loadPct}%`,
              background: loadPct > 80 ? "var(--error)" : loadPct > 50 ? "var(--warning)" : color,
            }}
          />
        </div>
      </div>

      <div className={styles.capSection}>
        <div className={styles.capGroup}>
          <span className={styles.capGroupLabel}>Capabilities</span>
          <div className={styles.tagRow}>
            {agent.capabilities.map((c) => (
              <span key={c} className={styles.capTag}>{c}</span>
            ))}
          </div>
        </div>
        <div className={styles.capGroup}>
          <span className={styles.capGroupLabel}>Tools</span>
          <div className={styles.tagRow}>
            {agent.tools.map((t) => (
              <span key={t} className={styles.toolTag}>{t}</span>
            ))}
          </div>
        </div>
      </div>

      <div className={styles.cardFooter}>
        <span className={styles.lastActive}>Last active {relativeTime(agent.lastActiveAt)}</span>
      </div>
    </div>
  );
}

function AgentSummaryRow({ agent, onClick, selected }: {
  agent: AgentInfo;
  onClick: () => void;
  selected: boolean;
}) {
  const loadPct = Math.round((agent.currentLoad / agent.maxConcurrent) * 100);
  return (
    <button
      className={`${styles.summaryRow} ${selected ? styles.summaryRowSelected : ""}`}
      onClick={onClick}
    >
      <span className={styles.summaryDot} data-status={agent.status} />
      <span className={styles.summaryName}>{agent.name}</span>
      <span className={styles.summaryStat}>{formatNumber(agent.tasksCompleted)}</span>
      <span className={styles.summaryStat} data-error={agent.tasksFailed > 10 ? "true" : "false"}>
        {agent.tasksFailed}
      </span>
      <span className={styles.summaryStat}>{formatDuration(agent.avgDurationMs)}</span>
      <div className={styles.summaryLoad}>
        <div className={styles.summaryLoadTrack}>
          <div
            className={styles.summaryLoadFill}
            style={{
              width: `${loadPct}%`,
              background: loadPct > 80 ? "var(--error)" : loadPct > 50 ? "var(--warning)" : "var(--green)",
            }}
          />
        </div>
        <span className={styles.summaryLoadTxt}>{loadPct}%</span>
      </div>
      <span className={styles.summaryStatus} data-status={agent.status}>
        {STATUS_LABELS[agent.status]}
      </span>
    </button>
  );
}

export default function AgentsPage() {
  const agents = useAgents();
  const metrics = useMetrics();
  const [selected, setSelected] = useState<string | null>(agents[0]?.name ?? null);

  const selectedAgent = agents.find((a) => a.name === selected);
  const onlineCount = agents.filter((a) => a.status === "online" || a.status === "busy").length;

  return (
    <div className={styles.page}>
      <PageHeader
        title="Agents"
        description="Agent registry — status, performance, and capability overview"
        badge={{ label: `${onlineCount}/${agents.length} online`, color: "green" }}
      />

      <div className={styles.body}>
        {/* Summary bar */}
        <div className={styles.summaryBar}>
          <div className={styles.sumStat}>
            <span className={styles.sumVal}>{agents.length}</span>
            <span className={styles.sumLbl}>Registered</span>
          </div>
          <div className={styles.sumStat}>
            <span className={styles.sumVal} style={{ color: "var(--green)" }}>{onlineCount}</span>
            <span className={styles.sumLbl}>Online</span>
          </div>
          <div className={styles.sumStat}>
            <span className={styles.sumVal}>{formatNumber(agents.reduce((a, b) => a + b.tasksCompleted, 0))}</span>
            <span className={styles.sumLbl}>Total Tasks</span>
          </div>
          <div className={styles.sumStat}>
            <span className={styles.sumVal}>{agents.reduce((a, b) => a + b.tasksFailed, 0)}</span>
            <span className={styles.sumLbl}>Total Failures</span>
          </div>
          <div className={styles.sumStat}>
            <span className={styles.sumVal}>{metrics.avgLatencyMs}ms</span>
            <span className={styles.sumLbl}>Avg Latency</span>
          </div>
          <div className={styles.sumStat}>
            <span className={styles.sumVal}>{metrics.activeWorkflows}</span>
            <span className={styles.sumLbl}>Active Wf.</span>
          </div>
        </div>

        <div className={styles.mainContent}>
          {/* Table */}
          <Panel title="Agent Registry" subtitle={`${agents.length} agents`} noPadding>
            <div className={styles.tableHeader}>
              <span className={styles.thCell}>Agent</span>
              <span className={styles.thCell}>Completed</span>
              <span className={styles.thCell}>Failed</span>
              <span className={styles.thCell}>Avg Dur.</span>
              <span className={styles.thCell}>Load</span>
              <span className={styles.thCell}>Status</span>
            </div>
            <div className={styles.tableBody}>
              {agents.map((a) => (
                <AgentSummaryRow
                  key={a.name}
                  agent={a}
                  selected={selected === a.name}
                  onClick={() => setSelected(a.name)}
                />
              ))}
            </div>
          </Panel>

          {/* Detail panel */}
          {selectedAgent ? (
            <AgentDetailCard agent={selectedAgent} />
          ) : (
            <div className={styles.detailEmpty}>
              Select an agent to view details
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
