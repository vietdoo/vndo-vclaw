"use client";

import { useRef, useEffect } from "react";
import styles from "./metric-card.module.css";

interface MetricCardProps {
  label: string;
  value: string | number;
  suffix?: string;
  subValue?: string;
  icon: React.ReactNode;
  trend?: "up" | "down" | "neutral";
  trendValue?: string;
  color?: "default" | "success" | "error" | "warning" | "blue" | "purple";
  compact?: boolean;
}

export function MetricCard({
  label, value, suffix, subValue, icon, trend, trendValue, color = "default", compact,
}: MetricCardProps) {
  const valueRef = useRef<HTMLSpanElement>(null);
  const prevValue = useRef(value);

  useEffect(() => {
    if (prevValue.current !== value && valueRef.current) {
      valueRef.current.classList.remove(styles.flash);
      void valueRef.current.offsetWidth;
      valueRef.current.classList.add(styles.flash);
    }
    prevValue.current = value;
  }, [value]);

  return (
    <div className={`${styles.card} ${compact ? styles.compact : ""}`} data-color={color}>
      <div className={styles.top}>
        <span className={styles.icon}>{icon}</span>
        <span className={styles.label}>{label}</span>
        {trend && trend !== "neutral" && (
          <span className={styles.trend} data-trend={trend}>
            {trend === "up" ? "↑" : "↓"}
            {trendValue && <span className={styles.trendVal}>{trendValue}</span>}
          </span>
        )}
      </div>
      <div className={styles.valueRow}>
        <span ref={valueRef} className={styles.value}>{value}</span>
        {suffix && <span className={styles.suffix}>{suffix}</span>}
      </div>
      {subValue && <span className={styles.subValue}>{subValue}</span>}
    </div>
  );
}
