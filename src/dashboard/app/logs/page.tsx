"use client";

import { useState, useMemo } from "react";
import { PageHeader } from "@/components/page-header";
import { Panel } from "@/components/panel";
import { useLogFeed } from "@/lib/hooks/use-realtime";
import { relativeTime } from "@/lib/utils";
import type { LogEntry } from "@/lib/types";
import styles from "./page.module.css";

const LEVEL_CONFIG: Record<LogEntry["level"], { label: string; color: string }> = {
  debug: { label: "DEBUG", color: "var(--text-tertiary)" },
  info: { label: "INFO", color: "var(--info)" },
  warning: { label: "WARN", color: "var(--warning)" },
  error: { label: "ERROR", color: "var(--error)" },
  critical: { label: "CRIT", color: "#ff0055" },
};

type LevelFilter = "all" | LogEntry["level"];

function LogRow({ log }: { log: LogEntry }) {
  const cfg = LEVEL_CONFIG[log.level];
  return (
    <div className={styles.logRow} data-level={log.level}>
      <span className={styles.logTime}>{relativeTime(log.timestamp)}</span>
      <span className={styles.logLevel} style={{ color: cfg.color }}>{cfg.label}</span>
      <span className={styles.logSource}>{log.source}</span>
      <span className={styles.logMessage}>{log.message}</span>
      {log.traceId && <span className={styles.logTrace}>{log.traceId}</span>}
    </div>
  );
}

export default function LogsPage() {
  const logs = useLogFeed(200);
  const [levelFilter, setLevelFilter] = useState<LevelFilter>("all");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [paused, setPaused] = useState(false);

  const sources = useMemo(() => {
    const s = new Set(logs.map((l) => l.source));
    return ["all", ...Array.from(s)];
  }, [logs]);

  const filtered = useMemo(() => {
    return logs.filter((l) => {
      if (levelFilter !== "all" && l.level !== levelFilter) return false;
      if (sourceFilter !== "all" && l.source !== sourceFilter) return false;
      if (search && !l.message.toLowerCase().includes(search.toLowerCase()) && !l.source.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [logs, levelFilter, sourceFilter, search]);

  const levelCounts = useMemo(() => {
    const counts: Partial<Record<LogEntry["level"], number>> = {};
    for (const l of logs) {
      counts[l.level] = (counts[l.level] ?? 0) + 1;
    }
    return counts;
  }, [logs]);

  const levels: { key: LevelFilter; label: string }[] = [
    { key: "all", label: "All" },
    { key: "debug", label: "Debug" },
    { key: "info", label: "Info" },
    { key: "warning", label: "Warn" },
    { key: "error", label: "Error" },
    { key: "critical", label: "Critical" },
  ];

  return (
    <div className={styles.page}>
      <PageHeader
        title="Logs"
        description="Structured platform logs with filtering and real-time streaming"
        live={!paused}
        badge={{ label: `${filtered.length} entries`, color: "gray" }}
      />

      <div className={styles.body}>
        {/* Level stats */}
        <div className={styles.levelStats}>
          {(Object.entries(LEVEL_CONFIG) as [LogEntry["level"], typeof LEVEL_CONFIG[LogEntry["level"]]][]).map(([key, cfg]) => (
            <button
              key={key}
              className={`${styles.levelStat} ${levelFilter === key ? styles.levelStatActive : ""}`}
              onClick={() => setLevelFilter(levelFilter === key ? "all" : key)}
              style={{ borderTopColor: cfg.color }}
            >
              <span className={styles.lsVal} style={{ color: cfg.color }}>{levelCounts[key] ?? 0}</span>
              <span className={styles.lsLabel}>{cfg.label}</span>
            </button>
          ))}
        </div>

        <Panel noPadding
          actions={
            <div className={styles.controls}>
              <input
                className={styles.searchInput}
                placeholder="Search messages..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <select
                className={styles.select}
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
              >
                {sources.map((s) => (
                  <option key={s} value={s}>{s === "all" ? "All sources" : s}</option>
                ))}
              </select>
              <div className={styles.filterRow}>
                {levels.map((l) => (
                  <button
                    key={l.key}
                    className={`${styles.filterBtn} ${levelFilter === l.key ? styles.filterBtnActive : ""}`}
                    onClick={() => setLevelFilter(l.key)}
                  >
                    {l.label}
                  </button>
                ))}
              </div>
              <button
                className={`${styles.pauseBtn} ${paused ? styles.pauseBtnActive : ""}`}
                onClick={() => setPaused((p) => !p)}
              >
                {paused ? "▶ Resume" : "⏸ Pause"}
              </button>
            </div>
          }
        >
          <div className={styles.logHeader}>
            <span>Time</span>
            <span>Level</span>
            <span>Source</span>
            <span>Message</span>
            <span>Trace</span>
          </div>
          <div className={styles.logBody}>
            {filtered.slice(0, 100).map((log) => (
              <LogRow key={log.id} log={log} />
            ))}
            {filtered.length === 0 && (
              <div className={styles.empty}>No logs match the current filters.</div>
            )}
          </div>
        </Panel>
      </div>
    </div>
  );
}
