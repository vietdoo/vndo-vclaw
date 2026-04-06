"use client";

import { Search, Bell, ChevronRight } from "lucide-react";
import { usePathname } from "next/navigation";
import styles from "./topbar.module.css";

const TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/agents": "Agents",
  "/workflows": "Workflows",
  "/events": "Events",
  "/logs": "Logs",
  "/requests": "Requests",
  "/infrastructure": "Infrastructure",
  "/security": "Security",
  "/settings": "Settings",
};

interface TopbarProps {
  environment?: string;
}

export function Topbar({ environment = "production" }: TopbarProps) {
  const pathname = usePathname();
  const title = TITLES[pathname] ?? "Dashboard";

  return (
    <header className={styles.topbar}>
      <div className={styles.left}>
        <div className={styles.breadcrumb}>
          <span className={styles.breadcrumbRoot}>vclaw</span>
          <ChevronRight size={12} className={styles.breadcrumbSep} />
          <span className={styles.breadcrumbCurrent}>{title}</span>
        </div>
      </div>
      <div className={styles.right}>
        <button className={styles.searchBtn}>
          <Search size={13} />
          <span>Search...</span>
          <kbd className={styles.kbd}>⌘K</kbd>
        </button>
        <div className={styles.envBadge} data-env={environment}>
          <span className={styles.envDot} />
          {environment}
        </div>
        <button className={styles.iconBtn}>
          <Bell size={14} />
        </button>
      </div>
    </header>
  );
}
