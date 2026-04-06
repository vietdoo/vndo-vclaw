"use client";

import { formatUptime } from "@/utils/format";

interface HeaderProps {
  connected: boolean;
  uptimeSeconds: number;
  activeTasks: number;
}

export function Header({ connected, uptimeSeconds, activeTasks }: HeaderProps) {
  return (
    <header className="h-14 border-b border-[var(--border)] flex items-center px-6 gap-6 flex-shrink-0 bg-[var(--bg)]">
      {/* logo */}
      <div className="flex items-center gap-2.5 mr-4">
        <div className="w-6 h-6 bg-[var(--accent)] rounded flex items-center justify-center">
          <span className="text-white text-xs font-bold leading-none">V</span>
        </div>
        <span className="text-sm font-semibold text-[var(--text-primary)] tracking-tight">
          vclaw
        </span>
        <span className="text-xs text-[var(--text-tertiary)] font-normal ml-1">/ dashboard</span>
      </div>

      <div className="flex-1" />

      {/* active tasks badge */}
      {activeTasks > 0 && (
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[var(--info-bg)] border border-[var(--info)]/20">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--info)] pulse-dot" />
          <span className="text-xs text-[var(--info)] font-medium tabular-nums">
            {activeTasks} running
          </span>
        </div>
      )}

      {/* uptime */}
      <div className="flex items-center gap-1.5 text-xs text-[var(--text-tertiary)]">
        <span className="font-mono">up {formatUptime(uptimeSeconds)}</span>
      </div>

      {/* connection status */}
      <div className="flex items-center gap-1.5">
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            connected ? "bg-[var(--success)] pulse-dot" : "bg-[var(--error)]"
          }`}
        />
        <span className="text-xs text-[var(--text-tertiary)]">
          {connected ? "live" : "reconnecting"}
        </span>
      </div>
    </header>
  );
}
