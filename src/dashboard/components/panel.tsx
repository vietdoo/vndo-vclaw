"use client";

import styles from "./panel.module.css";

interface PanelProps {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  noPadding?: boolean;
  live?: boolean;
}

export function Panel({ title, subtitle, children, actions, noPadding, live }: PanelProps) {
  return (
    <div className={styles.panel}>
      {(title || actions) && (
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            {title && <h2 className={styles.title}>{title}</h2>}
            {subtitle && <span className={styles.subtitle}>{subtitle}</span>}
            {live && (
              <span className={styles.live}>
                <span className={styles.liveDot} />
                Live
              </span>
            )}
          </div>
          {actions && <div className={styles.actions}>{actions}</div>}
        </div>
      )}
      <div className={noPadding ? styles.bodyNoPad : styles.body}>{children}</div>
    </div>
  );
}
