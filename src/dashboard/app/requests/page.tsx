"use client";

import { useRequestLog, useMetrics } from "@/lib/hooks/use-realtime";
import { formatDuration, relativeTime, formatNumber } from "@/lib/utils";
import { Activity, Circle } from "lucide-react";
import styles from "./page.module.css";

function getStatusColor(status: number): string {
  if (status < 300) return "green";
  if (status < 400) return "yellow";
  return "red";
}

export default function RequestsPage() {
  const requests = useRequestLog();
  const metrics = useMetrics();

  return (
    <div className={styles.root}>
      <div className={styles.pageHeader}>
        <div>
          <h1 className={styles.pageTitle}>Requests</h1>
          <p className={styles.pageDesc}>HTTP request log and API traffic monitor</p>
        </div>
        <div className={styles.liveRow}>
          <div className={styles.statChip}>
            <Activity size={11} />
            <span>{metrics.requestsPerMinute} req/min</span>
          </div>
          <div className={styles.statChip}>
            <span>{formatNumber(metrics.totalRequests)} total</span>
          </div>
          <span className={styles.liveBadge}>
            <Circle size={6} fill="var(--green)" stroke="none" className="animate-pulse" />
            Live
          </span>
        </div>
      </div>

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Method</th>
              <th>Path</th>
              <th>Status</th>
              <th>Duration</th>
              <th>Source</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {requests.map((req, i) => (
              <tr key={req.id} style={i === 0 ? { animation: "fadeIn 0.2s ease-out" } : undefined}>
                <td>
                  <span className={styles.methodBadge} data-method={req.method}>{req.method}</span>
                </td>
                <td className={styles.mono}>{req.path}</td>
                <td>
                  <span className={styles.statusBadge} data-color={getStatusColor(req.status)}>{req.status}</span>
                </td>
                <td className={styles.mono}>{formatDuration(req.durationMs)}</td>
                <td className={styles.dimText}>{req.source}</td>
                <td className={styles.dimText}>{relativeTime(req.timestamp)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
