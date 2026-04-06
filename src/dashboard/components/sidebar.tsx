"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  LayoutDashboard, Bot, GitBranch, Zap, ScrollText,
  Settings, Activity, Terminal, Shield, Database,
} from "lucide-react";
import styles from "./sidebar.module.css";

const NAV_SECTIONS = [
  {
    label: "Overview",
    items: [
      { href: "/", icon: LayoutDashboard, label: "Dashboard" },
      { href: "/agents", icon: Bot, label: "Agents" },
      { href: "/workflows", icon: GitBranch, label: "Workflows" },
    ],
  },
  {
    label: "Monitoring",
    items: [
      { href: "/events", icon: Zap, label: "Events" },
      { href: "/logs", icon: ScrollText, label: "Logs" },
      { href: "/requests", icon: Activity, label: "Requests" },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/infrastructure", icon: Database, label: "Infrastructure" },
      { href: "/security", icon: Shield, label: "Security" },
      { href: "/settings", icon: Settings, label: "Settings" },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className={styles.sidebar}>
      <div className={styles.logo}>
        <div className={styles.logoIcon}>
          <Terminal size={15} strokeWidth={2} />
        </div>
        <span className={styles.logoText}>vclaw</span>
        <span className={styles.version}>v0.1</span>
      </div>

      <nav className={styles.nav}>
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} className={styles.section}>
            <span className={styles.sectionLabel}>{section.label}</span>
            <ul className={styles.list}>
              {section.items.map((item) => {
                const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={`${styles.link} ${isActive ? styles.active : ""}`}
                    >
                      <item.icon size={14} strokeWidth={1.8} />
                      <span>{item.label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className={styles.footer}>
        <div className={styles.statusRow}>
          <span className={styles.statusDot} />
          <span className={styles.statusText}>All systems operational</span>
        </div>
      </div>
    </aside>
  );
}
