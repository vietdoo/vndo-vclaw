"use client";

interface WorkflowDonutProps {
  completed: number;
  failed: number;
  total: number;
}

export function WorkflowDonut({ completed, failed, total }: WorkflowDonutProps) {
  const r = 36;
  const cx = 48;
  const cy = 48;
  const circumference = 2 * Math.PI * r;

  const completedFrac = total > 0 ? completed / total : 0;
  const failedFrac = total > 0 ? failed / total : 0;
  const gapAngle = 0.015;

  const completedDash = completedFrac * circumference - gapAngle * r;
  const failedOffset = completedFrac * circumference;
  const failedDash = failedFrac * circumference - gapAngle * r;
  return (
    <div className="flex items-center gap-6">
      <svg width={96} height={96} viewBox="0 0 96 96" aria-hidden>
        {/* background track */}
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke="var(--bg-elevated)"
          strokeWidth={10}
        />

        {/* completed arc */}
        {completedFrac > 0 && (
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke="var(--success)"
            strokeWidth={10}
            strokeLinecap="butt"
            strokeDasharray={`${Math.max(0, completedDash)} ${circumference}`}
            strokeDashoffset={circumference * 0.25}
            transform={`rotate(-90 ${cx} ${cy})`}
          />
        )}

        {/* failed arc */}
        {failedFrac > 0 && (
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke="var(--error)"
            strokeWidth={10}
            strokeLinecap="butt"
            strokeDasharray={`${Math.max(0, failedDash)} ${circumference}`}
            strokeDashoffset={circumference * 0.25 - failedOffset}
            transform={`rotate(-90 ${cx} ${cy})`}
          />
        )}

        {/* center text */}
        <text
          x={cx}
          y={cy - 5}
          textAnchor="middle"
          fontSize={15}
          fontWeight={600}
          fill="var(--text-primary)"
        >
          {total > 0 ? `${((completedFrac) * 100).toFixed(0)}%` : "—"}
        </text>
        <text
          x={cx}
          y={cy + 11}
          textAnchor="middle"
          fontSize={9}
          fill="var(--text-tertiary)"
        >
          success
        </text>
      </svg>

      <div className="flex flex-col gap-2 text-xs">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[var(--success)]" />
          <span className="text-[var(--text-secondary)]">
            Completed <span className="text-[var(--text-primary)] font-medium tabular-nums">{completed}</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[var(--error)]" />
          <span className="text-[var(--text-secondary)]">
            Failed <span className="text-[var(--text-primary)] font-medium tabular-nums">{failed}</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[var(--bg-elevated)] border border-[var(--border-strong)]" />
          <span className="text-[var(--text-secondary)]">
            Total <span className="text-[var(--text-primary)] font-medium tabular-nums">{total}</span>
          </span>
        </div>
      </div>
    </div>
  );
}
