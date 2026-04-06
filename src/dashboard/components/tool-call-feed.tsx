"use client";

import type { ToolCall } from "@/lib/types";
import { formatDuration, relativeTime } from "@/lib/utils";
import styles from "./tool-call-feed.module.css";

interface ToolCallFeedProps {
  calls: ToolCall[];
  maxVisible?: number;
}

const STATUS_ICON: Record<ToolCall["status"], string> = {
  running: "◌",
  success: "✓",
  error: "✕",
  timeout: "⏱",
};

export function ToolCallFeed({ calls, maxVisible = 25 }: ToolCallFeedProps) {
  const visible = calls.slice(0, maxVisible);

  return (
    <div className={styles.container}>
      <div className={styles.feed}>
        {visible.map((call, i) => (
          <div
            key={call.id}
            className={styles.item}
            data-status={call.status}
          >
            <span className={styles.statusIcon} data-status={call.status}>
              {call.status === "running"
                ? <span className={styles.spinner}>◌</span>
                : STATUS_ICON[call.status]
              }
            </span>
            <div className={styles.content}>
              <div className={styles.topRow}>
                <span className={styles.toolName}>{call.toolName}</span>
                <span className={styles.time}>{relativeTime(call.timestamp)}</span>
              </div>
              <div className={styles.bottomRow}>
                <span className={styles.agentTag}>{call.agentName.replace("_", " ")}</span>
                <span className={styles.sep}>·</span>
                <span className={styles.wfId}>{call.workflowId}</span>
                {call.status !== "running" && call.durationMs > 0 && (
                  <>
                    <span className={styles.sep}>·</span>
                    <span className={styles.duration}>{formatDuration(call.durationMs)}</span>
                  </>
                )}
                {call.errorMsg && (
                  <span className={styles.errorMsg}>{call.errorMsg}</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
