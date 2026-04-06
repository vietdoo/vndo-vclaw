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
import styles from "./chart.module.css";

interface ThroughputChartProps {
  data: TimeSeriesPoint[];
}

export function ThroughputChart({ data }: ThroughputChartProps) {
  const chartData = useMemo(() => data, [data]);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3 className={styles.title}>Request Throughput</h3>
        <span className={styles.subtitle}>req/2s window</span>
      </div>
      <div className={styles.chartWrap}>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="reqGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#fff" stopOpacity={0.12} />
                <stop offset="100%" stopColor="#fff" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="errGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#e5484d" stopOpacity={0.2} />
                <stop offset="100%" stopColor="#e5484d" stopOpacity={0} />
              </linearGradient>
            </defs>
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
            />
            <Area
              type="monotone"
              dataKey="requests"
              stroke="#fff"
              strokeWidth={1.5}
              fill="url(#reqGradient)"
              dot={false}
              activeDot={{ r: 3, fill: "#fff" }}
            />
            <Area
              type="monotone"
              dataKey="errors"
              stroke="#e5484d"
              strokeWidth={1}
              fill="url(#errGradient)"
              dot={false}
              activeDot={{ r: 3, fill: "#e5484d" }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
