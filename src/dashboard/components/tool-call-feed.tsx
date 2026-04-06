"use client";

import type { ToolCall } from "@/lib/types";
import { formatDuration, relativeTime } from "@/lib/utils";
import styles from "./tool-call-feed.module.css";

interface ToolCallFeedProps {
  calls: ToolCall[];
}

const STATUS_ICON: Record<ToolCall["status"], string> = {
  running: "◌",
  success: "✓",
  error: "✕",
  timeout: "⏱",
};

export function ToolCallFeed({ calls }: ToolCallFeedProps) {
  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3 className={styles.title}>Tool Calls</h3>
        <div className={styles.legend}>
          <span className={styles.legendItem} data-status="running"><span className={styles.legendDot} /> Running</span>
          <span className={styles.legendItem} data-status="success"><span className={styles.legendDot} /> OK</span>
          <span className={styles.legendItem} data-status="error"><span className={styles.legendDot} /> Err</span>
        </div>
      </div>
      <div className={styles.feed}>
        {calls.map((call, i) => (
          <div
            key={call.id}
            className={styles.item}
            data-status={call.status}
            style={{ animationDelay: i === 0 ? "0ms" : undefined }}
          >
            <div className={styles.statusIcon} data-status={call.status}>
              {call.status === "running" ? (
                <span className="animate-pulse">{STATUS_ICON[call.status]}</span>
              ) : (
                STATUS_ICON[call.status]
              )}
            </div>
            <div className={styles.content}>
              <div className={styles.topRow}>
                <span className={styles.toolName}>{call.toolName}</span>
                <span className={styles.time}>{relativeTime(call.timestamp)}</span>
              </div>
              <div className={styles.bottomRow}>
                <span className={styles.agentName}>{call.agentName}</span>
                <span className={styles.divider}>·</span>
                <span className={styles.workflowId}>{call.workflowId}</span>
                {call.status !== "running" && (
                  <>
                    <span className={styles.divider}>·</span>
                    <span className={styles.duration}>{formatDuration(call.durationMs)}</span>
                  </>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
