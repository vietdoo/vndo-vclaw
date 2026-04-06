"use client";

import { ToolCallItem } from "@/utils/types";
import { formatTime, formatMs } from "@/utils/format";

interface ToolCallLogProps {
  items: ToolCallItem[];
}

export function ToolCallLog({ items }: ToolCallLogProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)]">
            <th className="text-left py-2.5 px-4 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
              Tool
            </th>
            <th className="text-left py-2.5 px-4 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
              Agent
            </th>
            <th className="text-right py-2.5 px-4 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
              Duration
            </th>
            <th className="text-right py-2.5 px-4 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
              Status
            </th>
            <th className="text-right py-2.5 px-4 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
              Time
            </th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td colSpan={5} className="py-8 text-center text-xs text-[var(--text-tertiary)]">
                No tool calls yet…
              </td>
            </tr>
          ) : (
            items.slice(0, 20).map((tc, idx) => (
              <tr
                key={tc.id}
                className={`border-b border-[var(--border)] hover:bg-[var(--bg-secondary)] transition-colors ${
                  idx === 0 ? "animate-slide-in" : ""
                }`}
              >
                <td className="py-2.5 px-4">
                  <span className="font-mono text-xs text-[var(--text-primary)]">{tc.toolName}</span>
                </td>
                <td className="py-2.5 px-4">
                  <span className="font-mono text-xs text-[var(--text-secondary)]">{tc.agentName}</span>
                </td>
                <td className="py-2.5 px-4 text-right font-mono text-xs tabular-nums text-[var(--text-secondary)]">
                  {tc.durationMs != null ? formatMs(tc.durationMs) : "…"}
                </td>
                <td className="py-2.5 px-4 text-right">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium ${
                      tc.status === "returned"
                        ? "bg-[var(--success-bg)] text-[var(--success)]"
                        : tc.status === "error"
                          ? "bg-[var(--error-bg)] text-[var(--error)]"
                          : "bg-[var(--bg-elevated)] text-[var(--text-tertiary)]"
                    }`}
                  >
                    {tc.status === "called" ? "pending" : tc.status}
                  </span>
                </td>
                <td className="py-2.5 px-4 text-right text-xs font-mono text-[var(--text-tertiary)]">
                  {formatTime(tc.ts)}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
