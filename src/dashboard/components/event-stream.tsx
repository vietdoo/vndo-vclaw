"use client";

import type { EventEntry } from "@/lib/types";
import { shortEventType, relativeTime } from "@/lib/utils";
import styles from "./event-stream.module.css";

interface EventStreamProps {
  events: EventEntry[];
  maxVisible?: number;
  compact?: boolean;
}

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
  "agent.registered": "blue",
};

function getColor(type: string): string {
  const short = shortEventType(type);
  return TYPE_COLORS[short] ?? "gray";
}

export function EventStream({ events, maxVisible = 30, compact }: EventStreamProps) {
  const visible = events.slice(0, maxVisible);

  return (
    <div className={styles.stream}>
      {visible.map((event) => (
        <div key={event.id} className={`${styles.event} ${compact ? styles.compact : ""}`}>
          <div className={styles.dotWrap}>
            <span className={styles.dot} data-color={getColor(event.type)} />
          </div>
          <div className={styles.content}>
            <div className={styles.topRow}>
              <span className={styles.type} data-color={getColor(event.type)}>
                {shortEventType(event.type)}
              </span>
              <span className={styles.time}>{relativeTime(event.timestamp)}</span>
            </div>
            {!compact && (
              <div className={styles.meta}>
                {event.workflowId && (
                  <span className={styles.metaItem}>{event.workflowId}</span>
                )}
                {typeof event.data.agent === "string" && (
                  <>
                    <span className={styles.sep}>·</span>
                    <span className={styles.metaItem}>{event.data.agent}</span>
                  </>
                )}
                {event.tenantId && (
                  <>
                    <span className={styles.sep}>·</span>
                    <span className={styles.metaItem}>{event.tenantId}</span>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
