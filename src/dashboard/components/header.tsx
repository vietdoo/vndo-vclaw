"use client";

import { formatUptime } from "@/lib/utils";
import styles from "./header.module.css";

interface HeaderProps {
  uptimeSeconds: number;
  environment?: string;
}

export function Header({ uptimeSeconds, environment = "production" }: HeaderProps) {
  return (
    <header className={styles.header}>
      <div className={styles.left}>
        <div className={styles.logo}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
          </svg>
          <span className={styles.title}>vclaw</span>
        </div>
        <span className={styles.separator}>/</span>
        <span className={styles.subtitle}>dashboard</span>
      </div>
      <div className={styles.right}>
        <div className={styles.badge} data-env={environment}>
          <span className={styles.dot} />
          {environment}
        </div>
        <div className={styles.uptime}>
          <span className={styles.uptimeLabel}>Uptime</span>
          <span className={styles.uptimeValue}>{formatUptime(uptimeSeconds)}</span>
        </div>
      </div>
    </header>
  );
}
