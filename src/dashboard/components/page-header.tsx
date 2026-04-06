"use client";

import styles from "./page-header.module.css";

interface PageHeaderProps {
  title: string;
  description?: string;
  children?: React.ReactNode;
  badge?: { label: string; color?: "green" | "yellow" | "red" | "blue" | "gray" };
  live?: boolean;
}

export function PageHeader({ title, description, children, badge, live }: PageHeaderProps) {
  return (
    <div className={styles.header}>
      <div className={styles.left}>
        <div className={styles.titleRow}>
          <h1 className={styles.title}>{title}</h1>
          {badge && (
            <span className={styles.badge} data-color={badge.color ?? "gray"}>
              {badge.label}
            </span>
          )}
          {live && (
            <span className={styles.livePill}>
              <span className={styles.liveDot} />
              Live
            </span>
          )}
        </div>
        {description && <p className={styles.description}>{description}</p>}
      </div>
      {children && <div className={styles.actions}>{children}</div>}
    </div>
  );
}
