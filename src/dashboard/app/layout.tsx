import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vclaw Dashboard",
  description: "Real-time monitoring dashboard for the Vclaw AI Agent Platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
