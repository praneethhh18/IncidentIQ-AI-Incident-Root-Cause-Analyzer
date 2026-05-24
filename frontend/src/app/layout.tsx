import "./globals.css";

import type { Metadata } from "next";
import { Github } from "lucide-react";

import { AuthBootstrap } from "@/components/AuthBootstrap";
import { ConditionalBackground } from "@/components/ConditionalBackground";
import { NavBar } from "@/components/NavBar";
import { ScrollProgress } from "@/components/ScrollProgress";
import { SessionChip } from "@/components/SessionChip";

export const metadata: Metadata = {
  title: "IncidentIQ. AI Incident Root Cause Analyzer.",
  description:
    "Connect Datadog, Grafana, and New Relic. IncidentIQ identifies the root cause, rebuilds the timeline, and recommends fixes in seconds.",
  metadataBase: new URL("http://localhost:3000"),
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen flex flex-col">
        <ConditionalBackground />
        <ScrollProgress />
        <AuthBootstrap />
        <NavBar />
        <main className="flex-1 w-full">{children}</main>
        <Footer />
      </body>
    </html>
  );
}

function Footer() {
  return (
    <footer className="border-t border-white/[0.05] text-ink-500 text-xs">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 py-5 flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap">
          <span>IncidentIQ. Built for on-call.</span>
          <SessionChip />
        </div>
        <a
          href="https://github.com/praneethhh18/IncidentIQ"
          className="flex items-center gap-1.5 hover:text-ink-300 transition"
          target="_blank"
          rel="noreferrer"
        >
          <Github className="size-3.5" /> source
        </a>
      </div>
    </footer>
  );
}
