"use client";

import { useEffect, useRef } from "react";

interface MetricCardProps {
  label: string;
  value: string | number;
  sub?: string;
  trend?: "up" | "down" | "neutral";
  trendValue?: string;
  accent?: boolean;
  mono?: boolean;
  children?: React.ReactNode;
}

export function MetricCard({
  label,
  value,
  sub,
  trend,
  trendValue,
  accent = false,
  mono = false,
  children,
}: MetricCardProps) {
  const valueRef = useRef<HTMLSpanElement>(null);
  const prevValue = useRef<string | number>(value);

  useEffect(() => {
    if (prevValue.current !== value && valueRef.current) {
      valueRef.current.classList.remove("value-updated");
      void valueRef.current.offsetWidth;
      valueRef.current.classList.add("value-updated");
      prevValue.current = value;
    }
  }, [value]);

  const trendColor =
    trend === "up"
      ? "text-[var(--success)]"
      : trend === "down"
        ? "text-[var(--error)]"
        : "text-[var(--text-tertiary)]";

  return (
    <div
      className={`rounded-lg border p-5 flex flex-col gap-3 transition-colors ${
        accent
          ? "bg-[var(--accent)] border-transparent text-white"
          : "bg-[var(--bg)] border-[var(--border)] hover:border-[var(--border-strong)]"
      }`}
    >
      <p
        className={`text-xs font-medium uppercase tracking-widest ${
          accent ? "text-white/60" : "text-[var(--text-tertiary)]"
        }`}
      >
        {label}
      </p>

      <div className="flex items-end justify-between gap-2">
        <span
          ref={valueRef}
          className={`text-3xl font-semibold leading-none tabular-nums ${
            mono ? "font-mono" : ""
          } ${accent ? "text-white" : "text-[var(--text-primary)]"}`}
        >
          {value}
        </span>

        {trendValue && (
          <span className={`text-xs font-medium pb-0.5 ${trendColor}`}>
            {trend === "up" ? "↑" : trend === "down" ? "↓" : ""}
            {trendValue}
          </span>
        )}
      </div>

      {sub && (
        <p className={`text-xs ${accent ? "text-white/50" : "text-[var(--text-tertiary)]"}`}>
          {sub}
        </p>
      )}

      {children}
    </div>
  );
}
