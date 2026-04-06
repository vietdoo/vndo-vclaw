"use client";

interface MiniBarChartProps {
  data: number[];
  height?: number;
  color?: string;
}

export function MiniBarChart({ data, height = 40, color = "var(--text-primary)" }: MiniBarChartProps) {
  if (!data.length) return null;

  const max = Math.max(...data, 1);
  const barWidth = 6;
  const gap = 3;
  const width = data.length * (barWidth + gap) - gap;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
      {data.map((v, i) => {
        const barH = Math.max(2, (v / max) * height);
        return (
          <rect
            key={i}
            x={i * (barWidth + gap)}
            y={height - barH}
            width={barWidth}
            height={barH}
            rx={1.5}
            fill={color}
            opacity={0.15 + (i / data.length) * 0.6}
          />
        );
      })}
    </svg>
  );
}
