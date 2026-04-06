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

interface AgentLoadChartProps {
  data: AgentLoadPoint[];
  height?: number;
}

const AGENT_COLORS: Record<string, string> = {
  task_management: "#0070f3",
  public_service: "#3dd68c",
  document_processor: "#8b5cf6",
  notification_hub: "#f5a623",
};

export function AgentLoadChart({ data, height = 160 }: AgentLoadChartProps) {
  const chartData = useMemo(() => data, [data]);
  const agents = useMemo(() => {
    if (!chartData.length) return [];
    return Object.keys(chartData[0]).filter((k) => k !== "time");
  }, [chartData]);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={chartData} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
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
        />
        {agents.map((agent) => (
          <Bar
            key={agent}
            dataKey={agent}
            fill={AGENT_COLORS[agent] ?? "#444"}
            radius={[2, 2, 0, 0]}
            maxBarSize={10}
            stackId="load"
            opacity={0.85}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
