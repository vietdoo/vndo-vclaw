"use client";

import { useState, useMemo } from "react";
import { PageHeader } from "@/components/page-header";
import { Panel } from "@/components/panel";
import { useEventFeed } from "@/lib/hooks/use-realtime";
import { shortEventType, relativeTime } from "@/lib/utils";
import type { EventEntry } from "@/lib/types";
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
  "agent.registered": "blue",
};

function getColor(type: string): string {
  return TYPE_COLORS[shortEventType(type)] ?? "gray";
}

function EventRow({ event }: { event: EventEntry }) {
  const color = getColor(event.type);
  return (
    <div className={styles.eventRow}>
      <span className={styles.evDot} data-color={color} />
      <div className={styles.evMain}>
        <span className={styles.evType}>{event.type}</span>
        {event.workflowId && (
          <span className={styles.evMeta}>{event.workflowId}</span>
        )}
      </div>
      <span className={styles.evSource}>{event.source}</span>
      {event.tenantId && <span className={styles.evTenant}>{event.tenantId}</span>}
      <span className={styles.evCorr}>{event.correlationId}</span>
      <span className={styles.evTime}>{relativeTime(event.timestamp)}</span>
      <span className={styles.evBadge} data-color={color}>{shortEventType(event.type)}</span>
    </div>
  );
}

export default function EventsPage() {
  const events = useEventFeed(200);
  const [typeFilter, setTypeFilter] = useState("all");
  const [search, setSearch] = useState("");

  const types = useMemo(() => {
    const s = new Set(events.map((e) => e.type));
    return ["all", ...Array.from(s)];
  }, [events]);

  const filtered = useMemo(() => {
    return events.filter((e) => {
      if (typeFilter !== "all" && e.type !== typeFilter) return false;
      if (search && !e.type.includes(search) && !e.correlationId.includes(search)) return false;
      return true;
    });
  }, [events, typeFilter, search]);

  const typeCounts = useMemo(() => {
    const r: Record<string, number> = {};
    for (const e of events) {
      const s = shortEventType(e.type);
      r[s] = (r[s] ?? 0) + 1;
    }
    return Object.entries(r).sort((a, b) => b[1] - a[1]);
  }, [events]);

  return (
    <div className={styles.page}>
      <PageHeader
        title="Events"
        description="CloudEvent stream — all platform events with correlation tracking"
        live
        badge={{ label: `${events.length} recent`, color: "gray" }}
      />

      <div className={styles.body}>
        <div className={styles.mainGrid}>
          {/* Event table */}
          <Panel noPadding
            actions={
              <div className={styles.controls}>
                <input
                  className={styles.searchInput}
                  placeholder="Search event type, correlation ID..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <select
                  className={styles.select}
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                >
                  {types.map((t) => (
                    <option key={t} value={t}>{t === "all" ? "All event types" : t}</option>
                  ))}
                </select>
                <span className={styles.count}>{filtered.length} events</span>
              </div>
            }
          >
            <div className={styles.tableHead}>
              <span />
              <span>Event / Workflow</span>
              <span>Source</span>
              <span>Tenant</span>
              <span>Correlation</span>
              <span>Time</span>
              <span>Type</span>
            </div>
            <div className={styles.tableBody}>
              {filtered.slice(0, 100).map((ev) => (
                <EventRow key={ev.id} event={ev} />
              ))}
              {filtered.length === 0 && (
                <div className={styles.empty}>No events match the current filters.</div>
              )}
            </div>
          </Panel>

          {/* Sidebar: event breakdown */}
          <Panel title="Event Breakdown" subtitle="by type">
            <div className={styles.breakdown}>
              {typeCounts.map(([type, count]) => {
                const max = typeCounts[0]?.[1] ?? 1;
                const color = getColor(`vclaw.${type}`);
                const colorVars: Record<string, string> = {
                  green: "var(--green)",
                  blue: "var(--info)",
                  red: "var(--error)",
                  yellow: "var(--warning)",
                  purple: "var(--purple)",
                  gray: "var(--text-tertiary)",
                };
                const barColor = colorVars[color] ?? "var(--text-tertiary)";
                return (
                  <div key={type} className={styles.bkRow}>
                    <span className={styles.bkType}>{type}</span>
                    <div className={styles.bkBarWrap}>
                      <div className={styles.bkBar} style={{ width: `${(count / max) * 100}%`, background: barColor }} />
                    </div>
                    <span className={styles.bkCount}>{count}</span>
                  </div>
                );
              })}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
