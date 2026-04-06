"use client";

import { useWorkflows, useMetrics } from "@/lib/hooks/use-realtime";
import { formatDuration, relativeTime, formatNumber } from "@/lib/utils";
import { GitBranch, CheckCircle2, XCircle, Clock, Loader2, AlertTriangle } from "lucide-react";
import styles from "./page.module.css";

const STATUS_ICONS: Record<string, React.ReactNode> = {
  completed: <CheckCircle2 size={11} />,
  running: <Loader2 size={11} />,
  failed: <XCircle size={11} />,
  queued: <Clock size={11} />,
  cancelled: <AlertTriangle size={11} />,
};

export default function WorkflowsPage() {
  const workflows = useWorkflows();
  const metrics = useMetrics();

  const running = workflows.filter((w) => w.status === "running").length;
  const completed = workflows.filter((w) => w.status === "completed").length;
  const failed = workflows.filter((w) => w.status === "failed").length;
  const queued = workflows.filter((w) => w.status === "queued").length;

  return (
    <div className={styles.root}>
      <div className={styles.pageHeader}>
        <div>
          <h1 className={styles.pageTitle}>Workflows</h1>
          <p className={styles.pageDesc}>Track workflow execution and lifecycle</p>
        </div>
        <div className={styles.summaryRow}>
          <span className={styles.stat}><span className={styles.dot} data-color="blue" /> {running} running</span>
          <span className={styles.stat}><span className={styles.dot} data-color="green" /> {completed} completed</span>
          <span className={styles.stat}><span className={styles.dot} data-color="red" /> {failed} failed</span>
          <span className={styles.stat}><span className={styles.dot} data-color="yellow" /> {queued} queued</span>
        </div>
      </div>

      <div className={styles.statsBar}>
        <div className={styles.statBox}>
          <span className={styles.statBoxLabel}>Total Workflows</span>
          <span className={styles.statBoxValue}>{formatNumber(metrics.totalWorkflows)}</span>
        </div>
        <div className={styles.statBox}>
          <span className={styles.statBoxLabel}>Active</span>
          <span className={styles.statBoxValue}>{metrics.activeWorkflows}</span>
        </div>
        <div className={styles.statBox}>
          <span className={styles.statBoxLabel}>Avg Latency</span>
          <span className={styles.statBoxValue}>{metrics.avgLatencyMs}ms</span>
        </div>
        <div className={styles.statBox}>
          <span className={styles.statBoxLabel}>Success Rate</span>
          <span className={styles.statBoxValue}>{metrics.successRate.toFixed(1)}%</span>
        </div>
      </div>

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>ID</th>
              <th>Status</th>
              <th>Agent</th>
              <th>Intent</th>
              <th>Source</th>
              <th>Steps</th>
              <th>Duration</th>
              <th>Tenant</th>
              <th>Started</th>
            </tr>
          </thead>
          <tbody>
            {workflows.map((wf) => (
              <tr key={wf.id}>
                <td className={styles.mono}>{wf.id}</td>
                <td>
                  <span className={styles.statusPill} data-status={wf.status}>
                    {STATUS_ICONS[wf.status]}
                    {wf.status}
                  </span>
                </td>
                <td className={styles.mono}>{wf.agentName}</td>
                <td>
                  <span className={styles.intentBadge}>{wf.intent}</span>
                </td>
                <td className={styles.dimText}>{wf.source}</td>
                <td className={styles.mono}>{wf.stepsCompleted}/{wf.steps}</td>
                <td className={styles.mono}>{wf.durationMs > 0 ? formatDuration(wf.durationMs) : "..."}</td>
                <td className={styles.dimText}>{wf.tenantId}</td>
                <td className={styles.dimText}>{relativeTime(wf.startedAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
