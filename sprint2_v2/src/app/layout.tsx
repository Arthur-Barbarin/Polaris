import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Polaris — Should you deploy drones here?",
  description:
    "Go/No-Go drone deployment analysis for commercial UAS operations. Sourced from FAA regulations, PwC industry research, and university studies. No synthetic scores.",
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
