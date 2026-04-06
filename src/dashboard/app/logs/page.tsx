"use client";

import { useLogs } from "@/lib/hooks/use-realtime";
import { relativeTime } from "@/lib/utils";
import { ScrollText, Circle } from "lucide-react";
import styles from "./page.module.css";

const LEVEL_COLORS: Record<string, string> = {
  debug: "gray",
  info: "blue",
  warn: "yellow",
  error: "red",
  fatal: "red",
};

export default function LogsPage() {
  const logs = useLogs();

  const counts = logs.reduce((acc, log) => {
    acc[log.level] = (acc[log.level] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className={styles.root}>
      <div className={styles.pageHeader}>
        <div>
          <h1 className={styles.pageTitle}>Logs</h1>
          <p className={styles.pageDesc}>Structured log viewer with real-time streaming</p>
        </div>
        <div className={styles.liveRow}>
          <span className={styles.levelChip} data-level="info">{counts.info || 0} info</span>
          <span className={styles.levelChip} data-level="warn">{counts.warn || 0} warn</span>
          <span className={styles.levelChip} data-level="error">{counts.error || 0} error</span>
          <span className={styles.liveBadge}>
            <Circle size={6} fill="var(--green)" stroke="none" className="animate-pulse" />
            Live
          </span>
        </div>
      </div>

      <div className={styles.logContainer}>
        <div className={styles.logHeader}>
          <span className={styles.colTime}>Time</span>
          <span className={styles.colLevel}>Level</span>
          <span className={styles.colSource}>Source</span>
          <span className={styles.colMessage}>Message</span>
          <span className={styles.colTrace}>Trace ID</span>
        </div>
        <div className={styles.logBody}>
          {logs.map((log, i) => {
            const color = LEVEL_COLORS[log.level] || "gray";
            return (
              <div
                key={log.id}
                className={styles.logRow}
                data-level={log.level}
                style={i === 0 ? { animation: "fadeIn 0.15s ease-out" } : undefined}
              >
                <span className={styles.colTime}>{relativeTime(log.timestamp)}</span>
                <span className={styles.colLevel}>
                  <span className={styles.levelBadge} data-color={color}>{log.level.toUpperCase()}</span>
                </span>
                <span className={styles.colSource}>{log.source}</span>
                <span className={styles.colMessage}>{log.message}</span>
                <span className={styles.colTrace}>{log.traceId ?? "—"}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
