"use client";

import { useMemo } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
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
        <span className={styles.subtitle}>req/2s</span>
      </div>
      <div className={styles.chartWrap}>
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
            <defs>
              <linearGradient id="reqGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#fff" stopOpacity={0.08} />
                <stop offset="100%" stopColor="#fff" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="errGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#e5484d" stopOpacity={0.15} />
                <stop offset="100%" stopColor="#e5484d" stopOpacity={0} />
              </linearGradient>
            </defs>
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
            />
            <Area type="monotone" dataKey="requests" stroke="#666" strokeWidth={1.5} fill="url(#reqGrad)" dot={false} activeDot={{ r: 2.5, fill: "#fff" }} />
            <Area type="monotone" dataKey="errors" stroke="#e5484d" strokeWidth={1} fill="url(#errGrad)" dot={false} activeDot={{ r: 2.5, fill: "#e5484d" }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
