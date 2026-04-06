"use client";

import { Settings, Globe, Bell, Cpu, Database, Key } from "lucide-react";
import styles from "./page.module.css";

const SETTINGS_GROUPS = [
  {
    title: "General",
    icon: <Settings size={13} />,
    items: [
      { label: "Platform Name", value: "vclaw", type: "text" },
      { label: "Environment", value: "production", type: "badge" },
      { label: "API Version", value: "v1", type: "text" },
      { label: "Debug Mode", value: "disabled", type: "badge-off" },
    ],
  },
  {
    title: "Networking",
    icon: <Globe size={13} />,
    items: [
      { label: "Webhook URL", value: "/webhook/telegram", type: "mono" },
      { label: "API Prefix", value: "/api/v1", type: "mono" },
      { label: "CORS Origins", value: "*", type: "mono" },
      { label: "Rate Limit", value: "100 req/min", type: "text" },
    ],
  },
  {
    title: "Notifications",
    icon: <Bell size={13} />,
    items: [
      { label: "Error Alerts", value: "enabled", type: "badge" },
      { label: "Slack Integration", value: "not configured", type: "badge-off" },
      { label: "Email Alerts", value: "not configured", type: "badge-off" },
    ],
  },
  {
    title: "Infrastructure",
    icon: <Database size={13} />,
    items: [
      { label: "PostgreSQL", value: "localhost:5432", type: "mono" },
      { label: "Redis", value: "localhost:6379", type: "mono" },
      { label: "Kafka Bootstrap", value: "localhost:9092", type: "mono" },
      { label: "LLM Provider", value: "OpenAI-compatible", type: "text" },
    ],
  },
  {
    title: "LLM Configuration",
    icon: <Cpu size={13} />,
    items: [
      { label: "Primary Provider", value: "openai", type: "text" },
      { label: "Model", value: "gpt-4o-mini", type: "mono" },
      { label: "Max Tokens", value: "4096", type: "mono" },
      { label: "Temperature", value: "0.1", type: "mono" },
      { label: "Fallback Provider", value: "ollama", type: "text" },
    ],
  },
  {
    title: "API Keys",
    icon: <Key size={13} />,
    items: [
      { label: "Telegram Bot Token", value: "••••••••", type: "secret" },
      { label: "OpenAI API Key", value: "••••••••", type: "secret" },
      { label: "OpenRouter Key", value: "••••••••", type: "secret" },
    ],
  },
];

export default function SettingsPage() {
  return (
    <div className={styles.root}>
      <div className={styles.pageHeader}>
        <div>
          <h1 className={styles.pageTitle}>Settings</h1>
          <p className={styles.pageDesc}>Platform configuration and environment settings</p>
        </div>
      </div>

      <div className={styles.grid}>
        {SETTINGS_GROUPS.map((group) => (
          <div key={group.title} className={styles.card}>
            <div className={styles.cardHeader}>
              {group.icon}
              <h2 className={styles.cardTitle}>{group.title}</h2>
            </div>
            <div className={styles.itemList}>
              {group.items.map((item) => (
                <div key={item.label} className={styles.item}>
                  <span className={styles.itemLabel}>{item.label}</span>
                  <span className={`${styles.itemValue} ${item.type === "mono" || item.type === "secret" ? styles.mono : ""}`} data-type={item.type}>
                    {item.value}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
