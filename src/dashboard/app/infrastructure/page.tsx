"use client";

import { useSystemStatus, useMetrics } from "@/lib/hooks/use-realtime";
import { formatNumber, formatUptime } from "@/lib/utils";
import {
  Cpu, HardDrive, Wifi, Database, Server, Activity,
  ArrowDown, ArrowUp, CheckCircle2, XCircle,
} from "lucide-react";
import styles from "./page.module.css";

function ProgressBar({ value, color = "blue" }: { value: number; color?: string }) {
  return (
    <div className={styles.progressBar}>
      <div className={styles.progressFill} data-color={color} style={{ width: `${Math.min(100, value)}%` }} />
    </div>
  );
}

function ServiceCard({ name, connected, icon }: { name: string; connected: boolean; icon: React.ReactNode }) {
  return (
    <div className={styles.serviceCard} data-ok={connected}>
      <div className={styles.serviceIcon}>{icon}</div>
      <div className={styles.serviceInfo}>
        <span className={styles.serviceName}>{name}</span>
        <span className={styles.serviceStatus} data-ok={connected}>
          {connected ? <><CheckCircle2 size={10} /> Connected</> : <><XCircle size={10} /> Disconnected</>}
        </span>
      </div>
    </div>
  );
}

export default function InfrastructurePage() {
  const system = useSystemStatus();
  const metrics = useMetrics();

  return (
    <div className={styles.root}>
      <div className={styles.pageHeader}>
        <div>
          <h1 className={styles.pageTitle}>Infrastructure</h1>
          <p className={styles.pageDesc}>System resources and service health monitoring</p>
        </div>
      </div>

      <div className={styles.servicesGrid}>
        <ServiceCard name="Redis" connected={system.redisConnected} icon={<Database size={14} />} />
        <ServiceCard name="Kafka" connected={system.kafkaConnected} icon={<Activity size={14} />} />
        <ServiceCard name="PostgreSQL" connected={system.postgresConnected} icon={<Database size={14} />} />
      </div>

      <div className={styles.resourceGrid}>
        <div className={styles.resourceCard}>
          <div className={styles.resourceHeader}>
            <Cpu size={13} />
            <span>CPU Usage</span>
            <span className={styles.resourceValue}>{system.cpu.toFixed(1)}%</span>
          </div>
          <ProgressBar value={system.cpu} color={system.cpu > 80 ? "red" : system.cpu > 60 ? "yellow" : "blue"} />
        </div>
        <div className={styles.resourceCard}>
          <div className={styles.resourceHeader}>
            <HardDrive size={13} />
            <span>Memory</span>
            <span className={styles.resourceValue}>{system.memory.toFixed(1)}%</span>
          </div>
          <ProgressBar value={system.memory} color={system.memory > 85 ? "red" : system.memory > 70 ? "yellow" : "blue"} />
        </div>
        <div className={styles.resourceCard}>
          <div className={styles.resourceHeader}>
            <Server size={13} />
            <span>Disk</span>
            <span className={styles.resourceValue}>{system.disk.toFixed(1)}%</span>
          </div>
          <ProgressBar value={system.disk} color={system.disk > 90 ? "red" : "blue"} />
        </div>
      </div>

      <div className={styles.networkGrid}>
        <div className={styles.netCard}>
          <div className={styles.netIcon}><ArrowDown size={12} /></div>
          <div>
            <span className={styles.netLabel}>Network In</span>
            <span className={styles.netValue}>{system.networkIn.toFixed(1)} MB/s</span>
          </div>
        </div>
        <div className={styles.netCard}>
          <div className={styles.netIcon}><ArrowUp size={12} /></div>
          <div>
            <span className={styles.netLabel}>Network Out</span>
            <span className={styles.netValue}>{system.networkOut.toFixed(1)} MB/s</span>
          </div>
        </div>
        <div className={styles.netCard}>
          <div className={styles.netIcon}><Wifi size={12} /></div>
          <div>
            <span className={styles.netLabel}>Active Connections</span>
            <span className={styles.netValue}>{system.activeConnections}</span>
          </div>
        </div>
        <div className={styles.netCard}>
          <div className={styles.netIcon}><Activity size={12} /></div>
          <div>
            <span className={styles.netLabel}>Uptime</span>
            <span className={styles.netValue}>{formatUptime(metrics.uptimeSeconds)}</span>
          </div>
        </div>
      </div>

      <div className={styles.infoGrid}>
        <div className={styles.infoCard}>
          <h3 className={styles.infoTitle}>Platform Metrics</h3>
          <div className={styles.infoList}>
            <div className={styles.infoRow}><span>Total Requests</span><span className={styles.mono}>{formatNumber(metrics.totalRequests)}</span></div>
            <div className={styles.infoRow}><span>Total Workflows</span><span className={styles.mono}>{formatNumber(metrics.totalWorkflows)}</span></div>
            <div className={styles.infoRow}><span>Total Events</span><span className={styles.mono}>{formatNumber(metrics.totalEvents)}</span></div>
            <div className={styles.infoRow}><span>Total Tool Calls</span><span className={styles.mono}>{formatNumber(metrics.totalToolCalls)}</span></div>
            <div className={styles.infoRow}><span>Active Workflows</span><span className={styles.mono}>{metrics.activeWorkflows}</span></div>
            <div className={styles.infoRow}><span>Queue Depth</span><span className={styles.mono}>{metrics.queueDepth}</span></div>
          </div>
        </div>
        <div className={styles.infoCard}>
          <h3 className={styles.infoTitle}>Performance</h3>
          <div className={styles.infoList}>
            <div className={styles.infoRow}><span>Avg Latency</span><span className={styles.mono}>{metrics.avgLatencyMs}ms</span></div>
            <div className={styles.infoRow}><span>p99 Latency</span><span className={styles.mono}>{metrics.p99LatencyMs}ms</span></div>
            <div className={styles.infoRow}><span>Success Rate</span><span className={styles.mono}>{metrics.successRate.toFixed(2)}%</span></div>
            <div className={styles.infoRow}><span>Error Rate</span><span className={styles.mono}>{metrics.errorRate.toFixed(2)}%</span></div>
            <div className={styles.infoRow}><span>Events / sec</span><span className={styles.mono}>{metrics.eventsPerSecond}</span></div>
            <div className={styles.infoRow}><span>Throughput</span><span className={styles.mono}>{metrics.requestsPerMinute} rpm</span></div>
          </div>
        </div>
      </div>
    </div>
  );
}
