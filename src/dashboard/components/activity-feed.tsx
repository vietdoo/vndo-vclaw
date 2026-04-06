"use client";

import type { RequestLogEntry, ToolCall } from "@/lib/types";
import { relativeTime, formatDuration } from "@/lib/utils";
import { ArrowUpRight, ArrowDownLeft, Wrench, Circle } from "lucide-react";
import styles from "./activity-feed.module.css";

interface ActivityFeedProps {
  requests: RequestLogEntry[];
  toolCalls: ToolCall[];
}

const STATUS_COLOR: Record<string, string> = {
  running: "blue",
  success: "green",
  error: "red",
  timeout: "yellow",
};

function getHttpColor(status: number): string {
  if (status < 300) return "green";
  if (status < 400) return "yellow";
  return "red";
}

export function ActivityFeed({ requests, toolCalls }: ActivityFeedProps) {
  const combined = [
    ...requests.map((r) => ({ kind: "request" as const, timestamp: r.timestamp, data: r })),
    ...toolCalls.map((t) => ({ kind: "tool" as const, timestamp: t.timestamp, data: t })),
  ].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()).slice(0, 20);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3 className={styles.title}>Real-time Activity</h3>
        <span className={styles.live}>
          <Circle size={6} fill="var(--green)" stroke="none" className="animate-pulse" />
          Live
        </span>
      </div>
      <div className={styles.feed}>
        {combined.map((item, i) => {
          if (item.kind === "request") {
            const req = item.data as RequestLogEntry;
            const color = getHttpColor(req.status);
            return (
              <div key={req.id} className={styles.row} style={i === 0 ? { animation: "slideUp 0.2s ease-out" } : undefined}>
                <div className={styles.rowIcon} data-color={color}>
                  {req.method === "POST" ? <ArrowUpRight size={11} /> : <ArrowDownLeft size={11} />}
                </div>
                <span className={styles.method} data-method={req.method}>{req.method}</span>
                <span className={styles.path}>{req.path}</span>
                <span className={styles.spacer} />
                <span className={styles.status} data-color={color}>{req.status}</span>
                <span className={styles.duration}>{formatDuration(req.durationMs)}</span>
                <span className={styles.time}>{relativeTime(req.timestamp)}</span>
              </div>
            );
          } else {
            const tool = item.data as ToolCall;
            const color = STATUS_COLOR[tool.status] || "gray";
            return (
              <div key={tool.id} className={styles.row} style={i === 0 ? { animation: "slideUp 0.2s ease-out" } : undefined}>
                <div className={styles.rowIcon} data-color={color}>
                  <Wrench size={11} />
                </div>
                <span className={styles.toolLabel}>TOOL</span>
                <span className={styles.toolName}>{tool.toolName}</span>
                <span className={styles.agentTag}>{tool.agentName}</span>
                <span className={styles.spacer} />
                <span className={styles.status} data-color={color}>{tool.status}</span>
                <span className={styles.duration}>{tool.durationMs > 0 ? formatDuration(tool.durationMs) : "..."}</span>
                <span className={styles.time}>{relativeTime(tool.timestamp)}</span>
              </div>
            );
          }
        })}
      </div>
    </div>
  );
}
