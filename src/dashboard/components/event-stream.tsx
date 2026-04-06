"use client";

import type { EventEntry } from "@/lib/types";
import { shortEventType, relativeTime } from "@/lib/utils";
import styles from "./event-stream.module.css";

interface EventStreamProps {
  events: EventEntry[];
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
};

function getColor(type: string): string {
  const short = shortEventType(type);
  return TYPE_COLORS[short] ?? "gray";
}

export function EventStream({ events }: EventStreamProps) {
  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2 className={styles.title}>Event Stream</h2>
        <span className={styles.live}>
          <span className={styles.liveDot} />
          Live
        </span>
      </div>
      <div className={styles.stream}>
        {events.map((event, i) => (
          <div
            key={event.id}
            className={styles.event}
            style={i === 0 ? { animation: "slideInRight 0.2s ease-out" } : undefined}
          >
            <div className={styles.timeline}>
              <span className={styles.dot} data-color={getColor(event.type)} />
              {i < events.length - 1 && <span className={styles.line} />}
            </div>
            <div className={styles.content}>
              <div className={styles.topRow}>
                <span className={styles.type} data-color={getColor(event.type)}>
                  {shortEventType(event.type)}
                </span>
                <span className={styles.time}>{relativeTime(event.timestamp)}</span>
              </div>
              <div className={styles.meta}>
                <span className={styles.corId}>{event.correlationId}</span>
                {typeof event.data.agent === "string" && (
                  <>
                    <span className={styles.sep}>·</span>
                    <span className={styles.agent}>{event.data.agent}</span>
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
