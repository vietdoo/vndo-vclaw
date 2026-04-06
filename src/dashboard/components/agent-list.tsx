"use client";

import type { AgentInfo } from "@/lib/types";
import { formatDuration, relativeTime } from "@/lib/utils";
import styles from "./agent-list.module.css";

interface AgentListProps {
  agents: AgentInfo[];
}

const STATUS_LABELS: Record<AgentInfo["status"], string> = {
  online: "Healthy",
  busy: "Busy",
  offline: "Offline",
  degraded: "Degraded",
};

export function AgentList({ agents }: AgentListProps) {
  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2 className={styles.title}>Agents</h2>
        <span className={styles.count}>{agents.length} registered</span>
      </div>
      <div className={styles.list}>
        {agents.map((agent) => (
          <div key={agent.name} className={styles.card}>
            <div className={styles.cardTop}>
              <div className={styles.nameRow}>
                <span className={styles.status} data-status={agent.status} />
                <span className={styles.name}>{agent.name}</span>
                <span className={styles.version}>v{agent.version}</span>
              </div>
              <span className={styles.statusText} data-status={agent.status}>
                {STATUS_LABELS[agent.status]}
              </span>
            </div>
            <div className={styles.statsRow}>
              <div className={styles.stat}>
                <span className={styles.statLabel}>Completed</span>
                <span className={styles.statValue}>{agent.tasksCompleted.toLocaleString()}</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statLabel}>Failed</span>
                <span className={styles.statValue} data-error={agent.tasksFailed > 0}>
                  {agent.tasksFailed}
                </span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statLabel}>Avg</span>
                <span className={styles.statValue}>{formatDuration(agent.avgDurationMs)}</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statLabel}>Load</span>
                <span className={styles.statValue}>
                  {agent.currentLoad}/{agent.maxConcurrent}
                </span>
              </div>
            </div>
            <div className={styles.toolsRow}>
              {agent.tools.map((tool) => (
                <span key={tool} className={styles.toolBadge}>
                  {tool}
                </span>
              ))}
            </div>
            <div className={styles.lastActive}>
              Last active {relativeTime(agent.lastActiveAt)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
