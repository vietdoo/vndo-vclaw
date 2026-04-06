"use client";

interface PanelProps {
  title: string;
  subtitle?: string;
  badge?: string | number;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  noPad?: boolean;
}

export function Panel({ title, subtitle, badge, action, children, className = "", noPad = false }: PanelProps) {
  return (
    <div
      className={`flex flex-col rounded-lg border border-[var(--border)] bg-[var(--bg)] overflow-hidden ${className}`}
    >
      {/* panel header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)] flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <h2 className="text-sm font-medium text-[var(--text-primary)]">{title}</h2>
          {badge !== undefined && (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-[var(--bg-elevated)] text-[var(--text-tertiary)] tabular-nums">
              {badge}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {subtitle && (
            <span className="text-xs text-[var(--text-tertiary)]">{subtitle}</span>
          )}
          {action}
        </div>
      </div>

      {/* panel body */}
      <div className={`flex-1 min-h-0 overflow-hidden ${noPad ? "" : "p-4"}`}>
        {children}
      </div>
    </div>
  );
}
