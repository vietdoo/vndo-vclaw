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
        <span className={styles.subtitle}>p50 · ms</span>
      </div>
      <div className={styles.chartWrap}>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
            <XAxis
              dataKey="time"
              tick={{ fill: "#555", fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: "#222" }}
              interval="preserveStartEnd"
              minTickGap={40}
            />
            <YAxis
              tick={{ fill: "#555", fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              width={40}
            />
            <Tooltip
              contentStyle={{
                background: "#111",
                border: "1px solid #333",
                borderRadius: "6px",
                fontSize: "12px",
                color: "#ededed",
              }}
              labelStyle={{ color: "#888" }}
              formatter={(value: number) => [`${value}ms`, "Latency"]}
            />
            <Line
              type="monotone"
              dataKey="latency"
              stroke="#0070f3"
              strokeWidth={1.5}
              dot={false}
              activeDot={{ r: 3, fill: "#0070f3" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
