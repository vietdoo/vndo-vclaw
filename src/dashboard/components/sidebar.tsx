"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import styles from "./sidebar.module.css";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  badge?: string | number;
}

function DashboardIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </svg>
  );
}

function AgentsIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <circle cx="12" cy="8" r="4" />
      <path d="M6 20v-2a6 6 0 0 1 12 0v2" />
      <circle cx="19" cy="8" r="2.5" />
      <circle cx="5" cy="8" r="2.5" />
    </svg>
  );
}

function WorkflowsIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <circle cx="5" cy="6" r="2" />
      <circle cx="19" cy="6" r="2" />
      <circle cx="12" cy="18" r="2" />
      <path d="M7 6h10M5 8v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8" />
      <line x1="12" y1="14" x2="12" y2="16" />
    </svg>
  );
}

function ToolsIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
    </svg>
  );
}

function LogsIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="8" y1="13" x2="16" y2="13" />
      <line x1="8" y1="17" x2="12" y2="17" />
    </svg>
  );
}

function EventsIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}

function MetricsIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

const primaryNav: NavItem[] = [
  { href: "/dashboard", label: "Overview", icon: <DashboardIcon /> },
  { href: "/agents", label: "Agents", icon: <AgentsIcon /> },
  { href: "/workflows", label: "Workflows", icon: <WorkflowsIcon /> },
  { href: "/tools", label: "Tool Calls", icon: <ToolsIcon /> },
  { href: "/logs", label: "Logs", icon: <LogsIcon /> },
  { href: "/events", label: "Events", icon: <EventsIcon /> },
  { href: "/metrics", label: "Metrics", icon: <MetricsIcon /> },
];

const bottomNav: NavItem[] = [
  { href: "/settings", label: "Settings", icon: <SettingsIcon /> },
];

interface NavLinkProps {
  item: NavItem;
  active: boolean;
}

function NavLink({ item, active }: NavLinkProps) {
  return (
    <Link href={item.href} className={`${styles.navLink} ${active ? styles.navLinkActive : ""}`}>
      <span className={styles.navIcon}>{item.icon}</span>
      <span className={styles.navLabel}>{item.label}</span>
      {item.badge !== undefined && (
        <span className={styles.navBadge}>{item.badge}</span>
      )}
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className={styles.sidebar}>
      <div className={styles.logoArea}>
        <Link href="/dashboard" className={styles.logo}>
          <div className={styles.logoIcon}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="currentColor" fillOpacity="0.9" />
              <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
              <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeOpacity="0.6" />
            </svg>
          </div>
          <span className={styles.logoText}>vclaw</span>
        </Link>
        <div className={styles.envBadge}>
          <span className={styles.envDot} />
          <span className={styles.envLabel}>production</span>
        </div>
      </div>

      <nav className={styles.nav}>
        <div className={styles.navSection}>
          <span className={styles.navSectionLabel}>Platform</span>
          {primaryNav.map((item) => (
            <NavLink
              key={item.href}
              item={item}
              active={pathname === item.href || pathname.startsWith(item.href + "/")}
            />
          ))}
        </div>
      </nav>

      <div className={styles.bottom}>
        {bottomNav.map((item) => (
          <NavLink
            key={item.href}
            item={item}
            active={pathname === item.href}
          />
        ))}
        <div className={styles.version}>v0.1.0</div>
      </div>
    </aside>
  );
}
