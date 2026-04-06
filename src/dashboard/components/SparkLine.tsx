"use client";

interface SparkLineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  strokeWidth?: number;
}

export function SparkLine({
  data,
  width = 120,
  height = 36,
  color = "var(--text-primary)",
  strokeWidth = 1.5,
}: SparkLineProps) {
  if (data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pad = 2;

  const points = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * (width - pad * 2);
    const y = height - pad - ((v - min) / range) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const polyline = points.join(" ");
  const last = points[points.length - 1].split(",");

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      fill="none"
      aria-hidden
    >
      <polyline
        points={polyline}
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
        strokeLinecap="round"
        fill="none"
        opacity="0.5"
      />
      {/* last point dot */}
      <circle
        cx={parseFloat(last[0])}
        cy={parseFloat(last[1])}
        r={2.5}
        fill={color}
        opacity="0.8"
      />
    </svg>
  );
}
