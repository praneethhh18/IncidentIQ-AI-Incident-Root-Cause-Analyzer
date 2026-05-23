import "./globals.css";

import type { Metadata } from "next";
import Link from "next/link";
import { Github } from "lucide-react";

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
        <NavBar />
        <main className="flex-1 w-full">{children}</main>
        <Footer />
      </body>
    </html>
  );
}

function NavBar() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/[0.05] bg-ink-950/70 backdrop-blur-xl">
      <div className="mx-auto max-w-7xl px-6 h-14 flex items-center justify-between">
        <Link
          href="/"
          className="font-semibold tracking-tight text-ink-50 text-[15px] hover:text-white transition"
        >
          IncidentIQ
          <span className="text-ink-400 font-normal">.</span>
        </Link>

        <nav className="flex items-center gap-6 text-[13px]">
          <Link
            href="/dashboard"
            className="text-ink-400 hover:text-ink-50 transition"
          >
            Dashboard
          </Link>
          <Link
            href="/incidents"
            className="text-ink-400 hover:text-ink-50 transition"
          >
            History
          </Link>
          <Link href="/dashboard" className="btn-primary px-3.5 py-1.5 text-[13px]">
            Analyze
          </Link>
        </nav>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="border-t border-white/[0.05] text-ink-500 text-xs">
      <div className="mx-auto max-w-7xl px-6 py-5 flex items-center justify-between">
        <div>IncidentIQ. Built for on-call.</div>
        <a
          href="https://github.com/praneethhh18/IncidentIQ-AI-Incident-Root-Cause-Analyzer"
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
