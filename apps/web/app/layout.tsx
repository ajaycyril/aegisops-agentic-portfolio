import type { Metadata } from "next";
import { Geist } from "next/font/google";

import { TooltipProvider } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "AegisOps | Live Agent Systems Lab",
  description:
    "Run and inspect production agentic workflows beside deterministic rule systems.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={cn("dark font-sans", geist.variable)}>
      <body><TooltipProvider>{children}</TooltipProvider></body>
    </html>
  );
}
