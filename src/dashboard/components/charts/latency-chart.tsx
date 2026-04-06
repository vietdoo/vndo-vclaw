"use client";

import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { TimeSeriesPoint } from "@/lib/types";

interface LatencyChartProps {
  data: TimeSeriesPoint[];
  height?: number;
}

export function LatencyChart({ data, height = 160 }: LatencyChartProps) {
  const chartData = useMemo(() => data, [data]);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis
          dataKey="time"
          tick={{ fill: "#444", fontSize: 9 }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
          minTickGap={60}
        />
        <YAxis
          tick={{ fill: "#444", fontSize: 9 }}
          tickLine={false}
          axisLine={false}
          width={32}
        />
        <Tooltip
          contentStyle={{
            background: "#111",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: "6px",
            fontSize: "11px",
            color: "#ededed",
            boxShadow: "0 4px 12px rgba(0,0,0,0.6)",
          }}
          labelStyle={{ color: "#666", marginBottom: "4px" }}
          formatter={(value: number) => [`${value}ms`, "p50"]}
        />
        <Line
          type="monotone"
          dataKey="latency"
          stroke="#3dd68c"
          strokeWidth={1.5}
          dot={false}
          activeDot={{ r: 3, fill: "#3dd68c", strokeWidth: 0 }}
        />
        <Line
          type="monotone"
          dataKey="p95"
          stroke="#f5a623"
          strokeWidth={1}
          strokeDasharray="4 2"
          dot={false}
          activeDot={{ r: 3, fill: "#f5a623", strokeWidth: 0 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
