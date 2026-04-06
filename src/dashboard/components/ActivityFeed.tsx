"use client";

import { ActivityItem } from "@/utils/types";
import { formatTime } from "@/utils/format";

interface ActivityFeedProps {
  items: ActivityItem[];
}

const kindIcon: Record<string, string> = {
  "workflow.started":   "◆",
  "workflow.completed": "✓",
  "workflow.failed":    "✗",
  "agent.dispatched":   "→",
  "agent.completed":    "✓",
  "agent.failed":       "✗",
  "tool.called":        "⚡",
  "tool.returned":      "↩",
};

const statusStyles: Record<string, { dot: string; label: string; bg: string }> = {
  success: {
    dot: "bg-[var(--success)]",
    label: "text-[var(--success)]",
    bg: "bg-[var(--success-bg)]",
  },
  error: {
    dot: "bg-[var(--error)]",
    label: "text-[var(--error)]",
    bg: "bg-[var(--error-bg)]",
  },
  info: {
    dot: "bg-[var(--info)]",
    label: "text-[var(--info)]",
    bg: "bg-[var(--info-bg)]",
  },
  warning: {
    dot: "bg-[var(--warning)]",
    label: "text-[var(--warning)]",
    bg: "bg-[var(--warning-bg)]",
  },
  pending: {
    dot: "bg-[var(--text-tertiary)]",
    label: "text-[var(--text-secondary)]",
    bg: "bg-[var(--bg-elevated)]",
  },
};

export function ActivityFeed({ items }: ActivityFeedProps) {
  return (
    <div className="flex flex-col overflow-hidden h-full">
      <div className="flex flex-col divide-y divide-[var(--border)] overflow-y-auto flex-1 min-h-0">
        {items.length === 0 && (
          <div className="flex items-center justify-center h-24 text-[var(--text-tertiary)] text-sm">
            Waiting for events…
          </div>
        )}
        {items.map((item, idx) => {
          const s = statusStyles[item.status];
          const icon = kindIcon[item.kind] ?? "·";
          return (
            <div
              key={item.id}
              className={`flex items-start gap-3 px-4 py-2.5 hover:bg-[var(--bg-secondary)] transition-colors ${
                idx === 0 ? "animate-slide-in" : ""
              }`}
            >
              {/* status dot */}
              <div className="mt-1.5 flex-shrink-0">
                <span className={`inline-block w-1.5 h-1.5 rounded-full ${s.dot}`} />
              </div>

              {/* content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-mono ${s.label}`}>{icon}</span>
                  <span className="text-sm font-medium text-[var(--text-primary)] truncate">
                    {item.label}
                  </span>
                </div>
                {item.sublabel && (
                  <p className="text-xs text-[var(--text-secondary)] mt-0.5 truncate">
                    {item.sublabel}
                  </p>
                )}
              </div>

              {/* right side */}
              <div className="flex-shrink-0 text-right">
                {item.meta && (
                  <p className="text-xs font-mono text-[var(--text-tertiary)]">{item.meta}</p>
                )}
                <p className="text-[10px] text-[var(--text-tertiary)] mt-0.5">
                  {formatTime(item.ts)}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
