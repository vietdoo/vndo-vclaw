"use client";

import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { AgentLoadPoint } from "@/lib/types";
import styles from "./chart.module.css";

interface AgentLoadChartProps {
  data: AgentLoadPoint[];
}

const AGENT_COLORS: Record<string, string> = {
  task_management: "#fff",
  public_service: "#0070f3",
  document_processor: "#8b5cf6",
  notification_hub: "#555",
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
        <span className={styles.subtitle}>concurrent tasks</span>
      </div>
      <div className={styles.chartWrap}>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
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
            {agents.map((agent) => (
              <Bar
                key={agent}
                dataKey={agent}
                fill={AGENT_COLORS[agent] ?? "#444"}
                radius={[2, 2, 0, 0]}
                maxBarSize={12}
                stackId="load"
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
