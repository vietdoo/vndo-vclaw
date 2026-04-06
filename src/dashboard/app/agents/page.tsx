"use client";

import { useAgents, useToolCallFeed } from "@/lib/hooks/use-realtime";
import { formatDuration, relativeTime, formatNumber } from "@/lib/utils";
import { Bot, CheckCircle2, XCircle, Clock, Wrench, Layers } from "lucide-react";
import styles from "./page.module.css";

const STATUS_LABELS: Record<string, string> = {
  online: "Healthy",
  busy: "Busy",
  offline: "Offline",
  degraded: "Degraded",
};

export default function AgentsPage() {
  const agents = useAgents();
  const toolCalls = useToolCallFeed();

  const totalCompleted = agents.reduce((a, b) => a + b.tasksCompleted, 0);
  const totalFailed = agents.reduce((a, b) => a + b.tasksFailed, 0);
  const avgRate = agents.length > 0 ? agents.reduce((a, b) => a + b.successRate, 0) / agents.length : 0;

  return (
    <div className={styles.root}>
      <div className={styles.pageHeader}>
        <div>
          <h1 className={styles.pageTitle}>Agents</h1>
          <p className={styles.pageDesc}>Monitor and manage registered AI agents</p>
        </div>
        <div className={styles.summaryRow}>
          <div className={styles.summaryItem}>
            <Bot size={12} />
            <span>{agents.length} registered</span>
          </div>
          <div className={styles.summaryItem}>
            <CheckCircle2 size={12} />
            <span>{formatNumber(totalCompleted)} completed</span>
          </div>
          <div className={styles.summaryItem}>
            <XCircle size={12} />
            <span>{totalFailed} failed</span>
          </div>
          <div className={styles.summaryItem}>
            <span>Avg success: {avgRate.toFixed(1)}%</span>
          </div>
        </div>
      </div>

      <div className={styles.agentGrid}>
        {agents.map((agent) => (
          <div key={agent.name} className={styles.agentCard}>
            <div className={styles.cardHeader}>
              <div className={styles.agentName}>
                <span className={styles.dot} data-status={agent.status} />
                <span className={styles.name}>{agent.name}</span>
                <span className={styles.version}>v{agent.version}</span>
              </div>
              <span className={styles.statusBadge} data-status={agent.status}>
                {STATUS_LABELS[agent.status]}
              </span>
            </div>

            <div className={styles.metricsRow}>
              <div className={styles.metric}>
                <CheckCircle2 size={10} />
                <span className={styles.metricLabel}>Completed</span>
                <span className={styles.metricValue}>{agent.tasksCompleted.toLocaleString()}</span>
              </div>
              <div className={styles.metric}>
                <XCircle size={10} />
                <span className={styles.metricLabel}>Failed</span>
                <span className={styles.metricValue} data-error={agent.tasksFailed > 100}>{agent.tasksFailed}</span>
              </div>
              <div className={styles.metric}>
                <Clock size={10} />
                <span className={styles.metricLabel}>Avg</span>
                <span className={styles.metricValue}>{formatDuration(agent.avgDurationMs)}</span>
              </div>
              <div className={styles.metric}>
                <span className={styles.metricLabel}>p99</span>
                <span className={styles.metricValue}>{formatDuration(agent.p99DurationMs)}</span>
              </div>
              <div className={styles.metric}>
                <Layers size={10} />
                <span className={styles.metricLabel}>Load</span>
                <span className={styles.metricValue}>{agent.currentLoad}/{agent.maxConcurrent}</span>
              </div>
              <div className={styles.metric}>
                <span className={styles.metricLabel}>Success</span>
                <span className={styles.metricValue}>{agent.successRate}%</span>
              </div>
            </div>

            <div className={styles.capabilitiesSection}>
              <span className={styles.sectionLabel}>Capabilities</span>
              <div className={styles.tagList}>
                {agent.capabilities.map((c) => (
                  <span key={c} className={styles.capTag}>{c}</span>
                ))}
              </div>
            </div>

            <div className={styles.toolsSection}>
              <span className={styles.sectionLabel}>
                <Wrench size={10} /> Tools
              </span>
              <div className={styles.tagList}>
                {agent.tools.map((t) => (
                  <span key={t} className={styles.toolTag}>{t}</span>
                ))}
              </div>
            </div>

            <div className={styles.cardFooter}>
              <span>Total: {agent.totalRequests.toLocaleString()} requests</span>
              <span>Last active {relativeTime(agent.lastActiveAt)}</span>
            </div>
          </div>
        ))}
      </div>

      <div className={styles.recentSection}>
        <h2 className={styles.sectionTitle}>Recent Tool Calls</h2>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Tool</th>
                <th>Agent</th>
                <th>Workflow</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {toolCalls.slice(0, 15).map((call) => (
                <tr key={call.id}>
                  <td className={styles.mono}>{call.toolName}</td>
                  <td>{call.agentName}</td>
                  <td className={styles.mono}>{call.workflowId}</td>
                  <td>
                    <span className={styles.statusPill} data-status={call.status}>{call.status}</span>
                  </td>
                  <td className={styles.mono}>{call.durationMs > 0 ? formatDuration(call.durationMs) : "..."}</td>
                  <td className={styles.dimText}>{relativeTime(call.timestamp)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
