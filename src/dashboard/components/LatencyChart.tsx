"use client";

interface LatencyChartProps {
  data: number[];
  avg: number;
  p99: number;
}

export function LatencyChart({ data, avg, p99 }: LatencyChartProps) {
  const width = 340;
  const height = 80;
  const padL = 40;
  const padR = 8;
  const padT = 8;
  const padB = 20;
  const chartW = width - padL - padR;
  const chartH = height - padT - padB;

  if (data.length < 2) {
    return (
      <div
        className="flex items-center justify-center text-xs text-[var(--text-tertiary)]"
        style={{ height }}
      >
        Collecting data…
      </div>
    );
  }

  const min = 0;
  const max = Math.max(...data, p99 * 1.1, 100);

  const toX = (i: number) => padL + (i / (data.length - 1)) * chartW;
  const toY = (v: number) => padT + chartH - ((v - min) / (max - min)) * chartH;

  const linePts = data.map((v, i) => `${toX(i).toFixed(1)},${toY(v).toFixed(1)}`).join(" ");
  const areaClose = `${toX(data.length - 1).toFixed(1)},${(padT + chartH).toFixed(1)} ${toX(0).toFixed(1)},${(padT + chartH).toFixed(1)}`;

  const yTicks = [0, Math.round(max / 2), Math.round(max)];

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} aria-hidden style={{ display: "block" }}>
      <defs>
        <linearGradient id="area-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--text-primary)" stopOpacity="0.12" />
          <stop offset="100%" stopColor="var(--text-primary)" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* y grid lines */}
      {yTicks.map((t) => (
        <g key={t}>
          <line
            x1={padL}
            y1={toY(t)}
            x2={width - padR}
            y2={toY(t)}
            stroke="var(--border)"
            strokeWidth={1}
          />
          <text
            x={padL - 4}
            y={toY(t) + 3}
            textAnchor="end"
            fontSize={9}
            fill="var(--text-tertiary)"
          >
            {t >= 1000 ? `${(t / 1000).toFixed(1)}s` : `${t}`}
          </text>
        </g>
      ))}

      {/* area fill */}
      <polyline
        points={`${linePts} ${areaClose}`}
        fill="url(#area-grad)"
        stroke="none"
      />

      {/* avg line */}
      <line
        x1={padL}
        y1={toY(avg)}
        x2={width - padR}
        y2={toY(avg)}
        stroke="var(--success)"
        strokeWidth={1}
        strokeDasharray="3 3"
        opacity={0.6}
      />

      {/* main line */}
      <polyline
        points={linePts}
        stroke="var(--text-primary)"
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
        fill="none"
      />

      {/* last point dot */}
      {data.length > 0 && (
        <circle
          cx={toX(data.length - 1)}
          cy={toY(data[data.length - 1])}
          r={2.5}
          fill="var(--text-primary)"
        />
      )}

      {/* legend */}
      <text x={padL + 2} y={padT + 10} fontSize={8} fill="var(--success)" opacity={0.8}>
        avg {avg.toFixed(0)}ms
      </text>
    </svg>
  );
}
