import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Polaris — Aviation SAF Scenario Explorer",
  description:
    "Test the coherence of your aviation SAF assumptions against IATA, ICAO, and ReFuelEU benchmarks. Built by Polaris Systems.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-900 antialiased">{children}</body>
    </html>
  );
}
