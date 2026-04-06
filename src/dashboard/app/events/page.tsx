"use client";

import { useEventFeed, useMetrics } from "@/lib/hooks/use-realtime";
import { shortEventType, relativeTime, formatNumber } from "@/lib/utils";
import { Zap, Circle } from "lucide-react";
import styles from "./page.module.css";

const TYPE_COLORS: Record<string, string> = {
  "message.received": "blue",
  "message.normalized": "blue",
  "intent.classified": "purple",
  "task.decomposed": "purple",
  "agent.dispatched": "yellow",
  "agent.completed": "green",
  "agent.failed": "red",
  "workflow.completed": "green",
  "workflow.failed": "red",
  "workflow.started": "blue",
  "tool.called": "cyan",
};

function getColor(type: string): string {
  return TYPE_COLORS[shortEventType(type)] ?? "gray";
}

export default function EventsPage() {
  const events = useEventFeed(50);
  const metrics = useMetrics();

  return (
    <div className={styles.root}>
      <div className={styles.pageHeader}>
        <div>
          <h1 className={styles.pageTitle}>Events</h1>
          <p className={styles.pageDesc}>Real-time CloudEvent stream from the platform</p>
        </div>
        <div className={styles.liveRow}>
          <div className={styles.statChip}>
            <Zap size={11} />
            <span>{metrics.eventsPerSecond} events/s</span>
          </div>
          <div className={styles.statChip}>
            <span>{formatNumber(metrics.totalEvents)} total</span>
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
              <th style={{ width: 30 }}></th>
              <th>Type</th>
              <th>Source</th>
              <th>Agent</th>
              <th>Correlation ID</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event, i) => {
              const color = getColor(event.type);
              return (
                <tr key={event.id} style={i === 0 ? { animation: "fadeIn 0.2s ease-out" } : undefined}>
                  <td>
                    <span className={styles.dot} data-color={color} />
                  </td>
                  <td>
                    <span className={styles.typeBadge} data-color={color}>
                      {shortEventType(event.type)}
                    </span>
                  </td>
                  <td className={styles.dimText}>{event.source}</td>
                  <td className={styles.mono}>{typeof event.data.agent === "string" ? event.data.agent : "—"}</td>
                  <td className={styles.mono}>{event.correlationId}</td>
                  <td className={styles.dimText}>{relativeTime(event.timestamp)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
