"use client";

import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Panel } from "@/components/panel";
import { useWorkflowFeed, useEventFeed } from "@/lib/hooks/use-realtime";
import { relativeTime, formatDuration } from "@/lib/utils";
import type { WorkflowEvent } from "@/lib/types";
import styles from "./page.module.css";

const STATUS_MAP: Record<WorkflowEvent["status"], { label: string; color: string }> = {
  completed: { label: "Completed", color: "green" },
  running: { label: "Running", color: "blue" },
  failed: { label: "Failed", color: "red" },
  pending: { label: "Pending", color: "gray" },
  timed_out: { label: "Timed Out", color: "yellow" },
};

const EVENT_TYPE_SHORT: Record<string, string> = {
  "vclaw.workflow.completed": "completed",
  "vclaw.workflow.failed": "failed",
  "vclaw.agent.dispatched": "agent dispatched",
  "vclaw.agent.completed": "agent completed",
  "vclaw.task.decomposed": "task decomposed",
};

function WorkflowRow({ wf }: { wf: WorkflowEvent }) {
  const s = STATUS_MAP[wf.status];
  return (
    <div className={styles.wfRow}>
      <div className={styles.wfId}>
        <span className={styles.wfIdText}>{wf.workflowId}</span>
        <span className={styles.wfEvent}>{EVENT_TYPE_SHORT[wf.eventType] ?? wf.eventType.replace("vclaw.", "")}</span>
      </div>
      <span className={styles.wfAgent}>{wf.agentName ?? "—"}</span>
      <span className={styles.wfDuration}>{wf.duration ? formatDuration(wf.duration) : "—"}</span>
      <span className={styles.wfTime}>{relativeTime(wf.timestamp)}</span>
      <span className={styles.wfStatus} data-color={s.color}>{s.label}</span>
    </div>
  );
}

type FilterStatus = "all" | WorkflowEvent["status"];

export default function WorkflowsPage() {
  const workflows = useWorkflowFeed(80);
  const events = useEventFeed(50);
  const [filter, setFilter] = useState<FilterStatus>("all");

  const filtered = filter === "all" ? workflows : workflows.filter((w) => w.status === filter);

  const counts = {
    completed: workflows.filter((w) => w.status === "completed").length,
    running: workflows.filter((w) => w.status === "running").length,
    failed: workflows.filter((w) => w.status === "failed").length,
    pending: workflows.filter((w) => w.status === "pending").length,
    timed_out: workflows.filter((w) => w.status === "timed_out").length,
  };

  const filters: { key: FilterStatus; label: string }[] = [
    { key: "all", label: "All" },
    { key: "running", label: "Running" },
    { key: "completed", label: "Completed" },
    { key: "failed", label: "Failed" },
    { key: "pending", label: "Pending" },
  ];

  return (
    <div className={styles.page}>
      <PageHeader
        title="Workflows"
        description="Real-time workflow execution tracking and event pipeline"
        live
      />

      <div className={styles.body}>
        {/* Status summary */}
        <div className={styles.statusRow}>
          {(Object.entries(counts) as [WorkflowEvent["status"], number][]).map(([key, val]) => {
            const s = STATUS_MAP[key];
            return (
              <div key={key} className={styles.statusCard} data-color={s.color}>
                <span className={styles.scVal}>{val}</span>
                <span className={styles.scLbl}>{s.label}</span>
              </div>
            );
          })}
        </div>

        <div className={styles.mainGrid}>
          {/* Workflow table */}
          <Panel
            title="Workflow Events"
            subtitle={`${filtered.length} entries`}
            live
            noPadding
            actions={
              <div className={styles.filterRow}>
                {filters.map((f) => (
                  <button
                    key={f.key}
                    className={`${styles.filterBtn} ${filter === f.key ? styles.filterBtnActive : ""}`}
                    onClick={() => setFilter(f.key)}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            }
          >
            <div className={styles.tableHead}>
              <span>Workflow / Event</span>
              <span>Agent</span>
              <span>Duration</span>
              <span>Time</span>
              <span>Status</span>
            </div>
            <div className={styles.tableBody}>
              {filtered.slice(0, 40).map((wf) => (
                <WorkflowRow key={wf.id} wf={wf} />
              ))}
              {filtered.length === 0 && (
                <div className={styles.emptyState}>No workflows match the selected filter.</div>
              )}
            </div>
          </Panel>

          {/* Event stream panel */}
          <Panel title="Event Pipeline" live noPadding>
            <div className={styles.eventPipeline}>
              {events.slice(0, 30).map((ev) => {
                const parts = ev.type.replace("vclaw.", "").split(".");
                const noun = parts[0];
                const verb = parts[1];
                const dotColors: Record<string, string> = {
                  message: "var(--info)",
                  intent: "var(--purple)",
                  agent: "var(--green)",
                  workflow: "var(--warning)",
                  task: "var(--purple)",
                };
                return (
                  <div key={ev.id} className={styles.pipelineItem}>
                    <div className={styles.pipeDot} style={{ background: dotColors[noun] ?? "var(--text-tertiary)" }} />
                    <div className={styles.pipeContent}>
                      <span className={styles.pipeType}>
                        <span className={styles.pipeNoun}>{noun}</span>
                        <span className={styles.pipeVerb}>.{verb}</span>
                      </span>
                      {ev.workflowId && (
                        <span className={styles.pipeMeta}>{ev.workflowId}</span>
                      )}
                    </div>
                    <span className={styles.pipeTime}>{relativeTime(ev.timestamp)}</span>
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
