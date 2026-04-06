"use client";

import { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import type { AgentLoadPoint } from "@/lib/types";
import styles from "./chart.module.css";

interface AgentLoadChartProps {
  data: AgentLoadPoint[];
}

const AGENT_COLORS: Record<string, string> = {
  task_management: "#666",
  public_service: "#0070f3",
  document_processor: "#8b5cf6",
  notification_hub: "#3fcf8e",
};

export function AgentLoadChart({ data }: AgentLoadChartProps) {
  const chartData = useMemo(() => data, [data]);
  const agents = useMemo(() => {
    if (!chartData.length) return [];
    return Object.keys(chartData[0]).filter((k) => k !== "time");
  }, [chartData]);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3 className={styles.title}>Agent Load</h3>
        <span className={styles.subtitle}>concurrent</span>
      </div>
      <div className={styles.chartWrap}>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={chartData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
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
            {agents.map((agent) => (
              <Bar key={agent} dataKey={agent} fill={AGENT_COLORS[agent] ?? "#333"} radius={[2, 2, 0, 0]} maxBarSize={10} stackId="load" />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
