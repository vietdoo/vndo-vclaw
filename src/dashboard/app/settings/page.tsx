"use client";

import { PageHeader } from "@/components/page-header";
import { Panel } from "@/components/panel";
import styles from "./page.module.css";

function SettingRow({ label, description, children }: {
  label: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={styles.settingRow}>
      <div className={styles.settingInfo}>
        <span className={styles.settingLabel}>{label}</span>
        {description && <span className={styles.settingDesc}>{description}</span>}
      </div>
      <div className={styles.settingControl}>{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <div className={styles.page}>
      <PageHeader
        title="Settings"
        description="Platform configuration and connection settings"
      />

      <div className={styles.body}>
        <Panel title="Backend Connection">
          <div className={styles.settings}>
            <SettingRow label="API Base URL" description="FastAPI monitoring service endpoint">
              <input
                className={styles.input}
                type="text"
                defaultValue="http://localhost:8000"
                placeholder="http://localhost:8000"
              />
            </SettingRow>
            <SettingRow label="WebSocket URL" description="Real-time events WebSocket endpoint">
              <input
                className={styles.input}
                type="text"
                defaultValue="ws://localhost:8000"
                placeholder="ws://localhost:8000"
              />
            </SettingRow>
            <SettingRow label="Refresh Interval" description="Dashboard data polling interval in milliseconds">
              <select className={styles.select} defaultValue="2000">
                <option value="1000">1 second</option>
                <option value="2000">2 seconds</option>
                <option value="5000">5 seconds</option>
                <option value="10000">10 seconds</option>
              </select>
            </SettingRow>
          </div>
        </Panel>

        <Panel title="Display">
          <div className={styles.settings}>
            <SettingRow label="Max Feed Items" description="Maximum number of items to show in live feeds">
              <select className={styles.select} defaultValue="50">
                <option value="20">20 items</option>
                <option value="50">50 items</option>
                <option value="100">100 items</option>
                <option value="200">200 items</option>
              </select>
            </SettingRow>
            <SettingRow label="Chart Time Window" description="Number of data points to display in charts">
              <select className={styles.select} defaultValue="40">
                <option value="20">20 points (~40s)</option>
                <option value="40">40 points (~80s)</option>
                <option value="60">60 points (~2m)</option>
              </select>
            </SettingRow>
            <SettingRow label="Compact Mode" description="Reduce spacing for information-dense display">
              <label className={styles.toggle}>
                <input type="checkbox" className={styles.toggleInput} />
                <span className={styles.toggleTrack}>
                  <span className={styles.toggleThumb} />
                </span>
              </label>
            </SettingRow>
          </div>
        </Panel>

        <Panel title="About">
          <div className={styles.about}>
            <div className={styles.aboutRow}>
              <span className={styles.aboutLabel}>Platform</span>
              <span className={styles.aboutValue}>Vclaw AI Agent Orchestration</span>
            </div>
            <div className={styles.aboutRow}>
              <span className={styles.aboutLabel}>Dashboard Version</span>
              <span className={styles.aboutValue} style={{ fontFamily: "var(--font-mono)" }}>v0.1.0</span>
            </div>
            <div className={styles.aboutRow}>
              <span className={styles.aboutLabel}>API Version</span>
              <span className={styles.aboutValue} style={{ fontFamily: "var(--font-mono)" }}>v1</span>
            </div>
            <div className={styles.aboutRow}>
              <span className={styles.aboutLabel}>Framework</span>
              <span className={styles.aboutValue}>Next.js 15 · React 19</span>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
