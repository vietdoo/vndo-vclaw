"use client";

import { useState, useMemo } from "react";
import { PageHeader } from "@/components/page-header";
import { Panel } from "@/components/panel";
import { useToolCallFeed, useMetrics } from "@/lib/hooks/use-realtime";
import { formatDuration, relativeTime, formatNumber } from "@/lib/utils";
import type { ToolCall } from "@/lib/types";
import styles from "./page.module.css";

const STATUS_CONFIG: Record<ToolCall["status"], { label: string; icon: string; color: string }> = {
  running: { label: "Running", icon: "◌", color: "var(--info)" },
  success: { label: "Success", icon: "✓", color: "var(--green)" },
  error: { label: "Error", icon: "✕", color: "var(--error)" },
  timeout: { label: "Timeout", icon: "⏱", color: "var(--warning)" },
};

function ToolCallRow({ call }: { call: ToolCall }) {
  const cfg = STATUS_CONFIG[call.status];
  return (
    <div className={styles.callRow} data-status={call.status}>
      <div className={styles.statusCell}>
        <span className={styles.statusIcon} style={{ color: cfg.color }}>
          {cfg.icon}
        </span>
      </div>
      <div className={styles.toolCell}>
        <span className={styles.toolName}>{call.toolName}</span>
        <span className={styles.callId}>{call.id}</span>
      </div>
      <span className={styles.agentCell}>{call.agentName.replace(/_/g, " ")}</span>
      <span className={styles.wfCell}>{call.workflowId}</span>
      <span className={styles.durCell}>{call.status !== "running" ? formatDuration(call.durationMs) : "—"}</span>
      <div className={styles.tokensCell}>
        {call.inputTokens !== undefined && (
          <span className={styles.tokenBadge} title="Input tokens">↑{call.inputTokens}</span>
        )}
        {call.outputTokens !== undefined && (
          <span className={styles.tokenBadge} title="Output tokens">↓{call.outputTokens}</span>
        )}
      </div>
      <span className={styles.timeCell}>{relativeTime(call.timestamp)}</span>
      <span className={styles.statusLabel} style={{ color: cfg.color }}>{cfg.label}</span>
    </div>
  );
}

type FilterStatus = "all" | ToolCall["status"];

export default function ToolsPage() {
  const calls = useToolCallFeed(200);
  const metrics = useMetrics();
  const [statusFilter, setStatusFilter] = useState<FilterStatus>("all");
  const [agentFilter, setAgentFilter] = useState("all");
  const [toolFilter, setToolFilter] = useState("all");
  const [search, setSearch] = useState("");

  const agents = useMemo(() => {
    const s = new Set(calls.map((c) => c.agentName));
    return ["all", ...Array.from(s)];
  }, [calls]);

  const tools = useMemo(() => {
    const s = new Set(calls.map((c) => c.toolName));
    return ["all", ...Array.from(s)];
  }, [calls]);

  const filtered = useMemo(() => {
    return calls.filter((c) => {
      if (statusFilter !== "all" && c.status !== statusFilter) return false;
      if (agentFilter !== "all" && c.agentName !== agentFilter) return false;
      if (toolFilter !== "all" && c.toolName !== toolFilter) return false;
      if (search && !c.toolName.includes(search) && !c.workflowId.includes(search)) return false;
      return true;
    });
  }, [calls, statusFilter, agentFilter, toolFilter, search]);

  const statusCounts = useMemo(() => {
    const r: Partial<Record<ToolCall["status"], number>> = {};
    for (const c of calls) r[c.status] = (r[c.status] ?? 0) + 1;
    return r;
  }, [calls]);

  const avgDuration = useMemo(() => {
    const done = calls.filter((c) => c.status !== "running" && c.durationMs > 0);
    if (!done.length) return 0;
    return Math.round(done.reduce((a, c) => a + c.durationMs, 0) / done.length);
  }, [calls]);

  const toolFreq = useMemo(() => {
    const freq: Record<string, number> = {};
    for (const c of calls) freq[c.toolName] = (freq[c.toolName] ?? 0) + 1;
    return Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 6);
  }, [calls]);

  const statusFilters: { key: FilterStatus; label: string }[] = [
    { key: "all", label: "All" },
    { key: "running", label: "Running" },
    { key: "success", label: "Success" },
    { key: "error", label: "Error" },
    { key: "timeout", label: "Timeout" },
  ];

  return (
    <div className={styles.page}>
      <PageHeader
        title="Tool Calls"
        description="Real-time LLM tool invocations — status, latency, and token usage"
        live
        badge={{ label: `${formatNumber(metrics.totalToolCalls)} total`, color: "gray" }}
      />

      <div className={styles.body}>
        {/* Summary row */}
        <div className={styles.summaryRow}>
          <div className={styles.sumCard}>
            <span className={styles.sumVal} style={{ color: "var(--green)" }}>
              {statusCounts.success ?? 0}
            </span>
            <span className={styles.sumLbl}>Succeeded</span>
          </div>
          <div className={styles.sumCard}>
            <span className={styles.sumVal} style={{ color: "var(--info)" }}>
              {statusCounts.running ?? 0}
            </span>
            <span className={styles.sumLbl}>Running</span>
          </div>
          <div className={styles.sumCard}>
            <span className={styles.sumVal} style={{ color: "var(--error)" }}>
              {statusCounts.error ?? 0}
            </span>
            <span className={styles.sumLbl}>Errors</span>
          </div>
          <div className={styles.sumCard}>
            <span className={styles.sumVal} style={{ color: "var(--warning)" }}>
              {statusCounts.timeout ?? 0}
            </span>
            <span className={styles.sumLbl}>Timeouts</span>
          </div>
          <div className={styles.sumCard}>
            <span className={styles.sumVal}>{formatDuration(avgDuration)}</span>
            <span className={styles.sumLbl}>Avg Duration</span>
          </div>
          <div className={styles.sumCard}>
            <span className={styles.sumVal}>{metrics.eventsPerSecond}</span>
            <span className={styles.sumLbl}>Calls / sec</span>
          </div>
        </div>

        <div className={styles.mainGrid}>
          {/* Main table */}
          <div className={styles.tablePanel}>
            <Panel noPadding
              actions={
                <div className={styles.controls}>
                  <input
                    className={styles.searchInput}
                    placeholder="Search tools, workflows..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                  <select className={styles.select} value={agentFilter} onChange={(e) => setAgentFilter(e.target.value)}>
                    {agents.map((a) => <option key={a} value={a}>{a === "all" ? "All agents" : a}</option>)}
                  </select>
                  <select className={styles.select} value={toolFilter} onChange={(e) => setToolFilter(e.target.value)}>
                    {tools.map((t) => <option key={t} value={t}>{t === "all" ? "All tools" : t}</option>)}
                  </select>
                  <div className={styles.filterRow}>
                    {statusFilters.map((f) => (
                      <button
                        key={f.key}
                        className={`${styles.filterBtn} ${statusFilter === f.key ? styles.filterBtnActive : ""}`}
                        onClick={() => setStatusFilter(f.key)}
                      >
                        {f.label}
                      </button>
                    ))}
                  </div>
                </div>
              }
            >
              <div className={styles.tableHead}>
                <span />
                <span>Tool</span>
                <span>Agent</span>
                <span>Workflow</span>
                <span>Duration</span>
                <span>Tokens</span>
                <span>Time</span>
                <span>Status</span>
              </div>
              <div className={styles.tableBody}>
                {filtered.slice(0, 80).map((call) => (
                  <ToolCallRow key={call.id} call={call} />
                ))}
                {filtered.length === 0 && (
                  <div className={styles.empty}>No tool calls match the current filters.</div>
                )}
              </div>
            </Panel>
          </div>

          {/* Sidebar: top tools */}
          <Panel title="Top Tools" subtitle="by call count">
            <div className={styles.toolFreq}>
              {toolFreq.map(([tool, count]) => {
                const max = toolFreq[0]?.[1] ?? 1;
                return (
                  <div key={tool} className={styles.freqRow}>
                    <span className={styles.freqTool}>{tool}</span>
                    <div className={styles.freqBarWrap}>
                      <div className={styles.freqBar} style={{ width: `${(count / max) * 100}%` }} />
                    </div>
                    <span className={styles.freqCount}>{count}</span>
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
