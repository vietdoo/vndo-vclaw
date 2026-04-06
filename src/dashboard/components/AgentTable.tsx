"use client";

import { useEffect, useState } from "react";
import { AgentStat } from "@/utils/types";
import { formatMs, formatTimeAgo } from "@/utils/format";

interface AgentTableProps {
  stats: Record<string, AgentStat>;
}

const KNOWN_AGENTS = [
  "task_management",
  "public_service",
  "search_agent",
  "summarizer",
  "code_reviewer",
];

export function AgentTable({ stats }: AgentTableProps) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 5000);
    return () => clearInterval(id);
  }, []);

  const all = KNOWN_AGENTS.map((agentName) => {
    const s = stats[agentName];
    return {
      name: agentName,
      calls: s?.calls ?? 0,
      errors: s?.errors ?? 0,
      avgDurationMs: s?.avgDurationMs ?? 0,
      lastSeen: s?.lastSeen ?? 0,
    };
  });

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)]">
            <th className="text-left py-2.5 px-4 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
              Agent
            </th>
            <th className="text-right py-2.5 px-4 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
              Calls
            </th>
            <th className="text-right py-2.5 px-4 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
              Errors
            </th>
            <th className="text-right py-2.5 px-4 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
              Avg Latency
            </th>
            <th className="text-right py-2.5 px-4 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
              Last Seen
            </th>
            <th className="text-right py-2.5 px-4 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {all.map((agent) => {
            const active = agent.lastSeen > 0 && now - agent.lastSeen < 15_000;
            const recentlyActive = agent.lastSeen > 0 && now - agent.lastSeen < 60_000;

            return (
              <tr
                key={agent.name}
                className="border-b border-[var(--border)] hover:bg-[var(--bg-secondary)] transition-colors"
              >
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2.5">
                    <span
                      className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                        active
                          ? "bg-[var(--success)] pulse-dot"
                          : recentlyActive
                            ? "bg-[var(--warning)]"
                            : "bg-[var(--border-strong)]"
                      }`}
                    />
                    <span className="font-mono text-xs text-[var(--text-primary)]">
                      {agent.name}
                    </span>
                  </div>
                </td>
                <td className="py-3 px-4 text-right font-mono text-xs tabular-nums text-[var(--text-secondary)]">
                  {agent.calls.toLocaleString()}
                </td>
                <td className="py-3 px-4 text-right">
                  <span
                    className={`font-mono text-xs tabular-nums ${
                      agent.errors > 0 ? "text-[var(--error)]" : "text-[var(--text-tertiary)]"
                    }`}
                  >
                    {agent.errors}
                  </span>
                </td>
                <td className="py-3 px-4 text-right font-mono text-xs tabular-nums text-[var(--text-secondary)]">
                  {agent.avgDurationMs > 0 ? formatMs(agent.avgDurationMs) : "—"}
                </td>
                <td className="py-3 px-4 text-right text-xs text-[var(--text-tertiary)]">
                  {agent.lastSeen > 0 ? formatTimeAgo(agent.lastSeen) : "never"}
                </td>
                <td className="py-3 px-4 text-right">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium ${
                      active
                        ? "bg-[var(--success-bg)] text-[var(--success)]"
                        : recentlyActive
                          ? "bg-[var(--warning-bg)] text-[var(--warning)]"
                          : "bg-[var(--bg-elevated)] text-[var(--text-tertiary)]"
                    }`}
                  >
                    {active ? "active" : recentlyActive ? "idle" : "offline"}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
