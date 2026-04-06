import type { Metadata } from "next";
import { Sidebar } from "@/components/sidebar";
import "./globals.css";
import styles from "./layout.module.css";

export const metadata: Metadata = {
  title: { default: "Vclaw", template: "%s · Vclaw" },
  description: "Real-time monitoring dashboard for the Vclaw AI Agent Platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className={styles.shell}>
          <Sidebar />
          <div className={styles.content}>
            {children}
          </div>
        </div>
      </body>
    </html>
  );
}
