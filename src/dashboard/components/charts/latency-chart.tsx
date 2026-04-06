"use client";

import { useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import type { TimeSeriesPoint } from "@/lib/types";
import styles from "./chart.module.css";

interface LatencyChartProps {
  data: TimeSeriesPoint[];
}

export function LatencyChart({ data }: LatencyChartProps) {
  const chartData = useMemo(() => data, [data]);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3 className={styles.title}>Latency</h3>
        <span className={styles.subtitle}>p50 / p99 · ms</span>
      </div>
      <div className={styles.chartWrap}>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={chartData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" vertical={false} />
            <XAxis
              dataKey="time" tick={{ fill: "#444", fontSize: 9 }}
              tickLine={false} axisLine={{ stroke: "#1a1a1a" }}
              interval="preserveStartEnd" minTickGap={50}
            />
            <YAxis
              tick={{ fill: "#444", fontSize: 9 }}
              tickLine={false} axisLine={false} width={36}
            />
            <Tooltip
              contentStyle={{ background: "#111", border: "1px solid #2a2a2a", borderRadius: "6px", fontSize: "11px", color: "#ededed" }}
              labelStyle={{ color: "#666", fontSize: "10px" }}
              formatter={(value: number, name: string) => [`${value}ms`, name === "latency" ? "p50" : "p99"]}
            />
            <Line type="monotone" dataKey="latency" stroke="#0070f3" strokeWidth={1.5} dot={false} activeDot={{ r: 2.5, fill: "#0070f3" }} />
            <Line type="monotone" dataKey="p99" stroke="#8b5cf6" strokeWidth={1} strokeDasharray="4 2" dot={false} activeDot={{ r: 2.5, fill: "#8b5cf6" }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
