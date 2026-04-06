"use client";

import { useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { TimeSeriesPoint } from "@/lib/types";

interface ThroughputChartProps {
  data: TimeSeriesPoint[];
  height?: number;
}

export function ThroughputChart({ data, height = 160 }: ThroughputChartProps) {
  const chartData = useMemo(() => data, [data]);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
        <defs>
          <linearGradient id="reqGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0070f3" stopOpacity={0.25} />
            <stop offset="100%" stopColor="#0070f3" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="errGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ff4444" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#ff4444" stopOpacity={0} />
          </linearGradient>
        </defs>
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
          itemStyle={{ color: "#aaa" }}
        />
        <Area
          type="monotone"
          dataKey="requests"
          stroke="#0070f3"
          strokeWidth={1.5}
          fill="url(#reqGrad)"
          dot={false}
          activeDot={{ r: 3, fill: "#0070f3", strokeWidth: 0 }}
        />
        <Area
          type="monotone"
          dataKey="errors"
          stroke="#ff4444"
          strokeWidth={1}
          fill="url(#errGrad)"
          dot={false}
          activeDot={{ r: 3, fill: "#ff4444", strokeWidth: 0 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
