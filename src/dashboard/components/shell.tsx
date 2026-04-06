"use client";

import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import styles from "./shell.module.css";

interface ShellProps {
  children: React.ReactNode;
}

export function Shell({ children }: ShellProps) {
  return (
    <div className={styles.shell}>
      <Sidebar />
      <div className={styles.content}>
        <Topbar />
        <main className={styles.main}>
          {children}
        </main>
      </div>
    </div>
  );
}
