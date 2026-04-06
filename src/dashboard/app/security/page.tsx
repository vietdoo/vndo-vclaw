"use client";

import { Shield, Key, Lock, UserCheck, AlertTriangle, CheckCircle2 } from "lucide-react";
import styles from "./page.module.css";

const AUDIT_LOG = [
  { id: "1", action: "API key created", user: "admin", timestamp: "2 min ago", severity: "info" },
  { id: "2", action: "Rate limit exceeded", user: "t-1003", timestamp: "8 min ago", severity: "warning" },
  { id: "3", action: "Failed authentication attempt", user: "unknown", timestamp: "15 min ago", severity: "error" },
  { id: "4", action: "Agent registered", user: "system", timestamp: "1h ago", severity: "info" },
  { id: "5", action: "Permission updated", user: "admin", timestamp: "2h ago", severity: "info" },
  { id: "6", action: "Webhook secret rotated", user: "admin", timestamp: "3h ago", severity: "info" },
  { id: "7", action: "Suspicious activity detected", user: "t-1001", timestamp: "5h ago", severity: "warning" },
  { id: "8", action: "SSL certificate renewed", user: "system", timestamp: "1d ago", severity: "info" },
];

export default function SecurityPage() {
  return (
    <div className={styles.root}>
      <div className={styles.pageHeader}>
        <div>
          <h1 className={styles.pageTitle}>Security</h1>
          <p className={styles.pageDesc}>Access control, authentication, and audit logging</p>
        </div>
      </div>

      <div className={styles.statusGrid}>
        <div className={styles.statusCard} data-ok="true">
          <Lock size={14} />
          <div>
            <span className={styles.statusLabel}>TLS/SSL</span>
            <span className={styles.statusValue}><CheckCircle2 size={10} /> Active</span>
          </div>
        </div>
        <div className={styles.statusCard} data-ok="true">
          <Key size={14} />
          <div>
            <span className={styles.statusLabel}>API Keys</span>
            <span className={styles.statusValue}>3 active</span>
          </div>
        </div>
        <div className={styles.statusCard} data-ok="true">
          <Shield size={14} />
          <div>
            <span className={styles.statusLabel}>Rate Limiting</span>
            <span className={styles.statusValue}><CheckCircle2 size={10} /> Enabled</span>
          </div>
        </div>
        <div className={styles.statusCard} data-ok="true">
          <UserCheck size={14} />
          <div>
            <span className={styles.statusLabel}>Webhook Verification</span>
            <span className={styles.statusValue}><CheckCircle2 size={10} /> Enabled</span>
          </div>
        </div>
      </div>

      <div className={styles.auditSection}>
        <h2 className={styles.sectionTitle}>Audit Log</h2>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Action</th>
                <th>User</th>
                <th>Severity</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {AUDIT_LOG.map((entry) => (
                <tr key={entry.id}>
                  <td>{entry.action}</td>
                  <td className={styles.mono}>{entry.user}</td>
                  <td>
                    <span className={styles.severityBadge} data-severity={entry.severity}>
                      {entry.severity === "warning" && <AlertTriangle size={9} />}
                      {entry.severity}
                    </span>
                  </td>
                  <td className={styles.dimText}>{entry.timestamp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
