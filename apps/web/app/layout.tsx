import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AegisOps Agentic Workflow Portfolio",
  description: "A production-grade visual command center for enterprise agentic workflows.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
