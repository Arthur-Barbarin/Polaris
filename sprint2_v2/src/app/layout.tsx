import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Polaris — Drone Deployment Decision Engine",
  description:
    "Go/No-Go deployment analysis for commercial UAS operations. Benchmark-referenced against FAA-107, FAA-108, PwC-2016, MU-EXT, BARCLAYS-2026.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
