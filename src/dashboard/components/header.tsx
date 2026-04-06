"use client";

import { formatUptime } from "@/lib/utils";
import { Clock, Cpu, HardDrive, Wifi } from "lucide-react";
import type { SystemStatus } from "@/lib/types";
import styles from "./header.module.css";

interface StatusBarProps {
  uptimeSeconds: number;
  systemStatus: SystemStatus;
}

export function StatusBar({ uptimeSeconds, systemStatus }: StatusBarProps) {
  return (
    <div className={styles.bar}>
      <div className={styles.barGroup}>
        <Clock size={11} />
        <span className={styles.barLabel}>Uptime</span>
        <span className={styles.barValue}>{formatUptime(uptimeSeconds)}</span>
      </div>
      <span className={styles.barDivider} />
      <div className={styles.barGroup}>
        <Cpu size={11} />
        <span className={styles.barLabel}>CPU</span>
        <span className={styles.barValue} data-warn={systemStatus.cpu > 70}>{systemStatus.cpu.toFixed(0)}%</span>
      </div>
      <span className={styles.barDivider} />
      <div className={styles.barGroup}>
        <HardDrive size={11} />
        <span className={styles.barLabel}>Memory</span>
        <span className={styles.barValue} data-warn={systemStatus.memory > 80}>{systemStatus.memory.toFixed(0)}%</span>
      </div>
      <span className={styles.barDivider} />
      <div className={styles.barGroup}>
        <Wifi size={11} />
        <span className={styles.barLabel}>Connections</span>
        <span className={styles.barValue}>{systemStatus.activeConnections}</span>
      </div>
      <div className={styles.barRight}>
        <ServiceDot label="Redis" ok={systemStatus.redisConnected} />
        <ServiceDot label="Kafka" ok={systemStatus.kafkaConnected} />
        <ServiceDot label="Postgres" ok={systemStatus.postgresConnected} />
      </div>
    </div>
  );
}

function ServiceDot({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className={styles.serviceDot}>
      <span className={styles.dot} data-ok={ok} />
      <span className={styles.serviceLabel}>{label}</span>
    </div>
  );
}
