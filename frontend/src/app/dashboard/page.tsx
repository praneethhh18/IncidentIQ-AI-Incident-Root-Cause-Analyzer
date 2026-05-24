import { Suspense } from "react";
import Link from "next/link";
import { ArrowUpRight, Cpu, History as HistoryIcon } from "lucide-react";

import { api } from "@/lib/api";
import type {
  IncidentSummary,
  IntegrationStatus,
  SampleIncident,
} from "@/lib/types";
import { AnalyzePanel } from "@/components/AnalyzePanel";
import { WatchToggle } from "@/components/WatchToggle";

export const dynamic = "force-dynamic";

interface HealthResponse {
  status: string;
  bedrock_enabled: boolean;
  model: string;
}

export default async function DashboardPage() {
  const [samples, integrations, health, recent] = await Promise.all([
    api.samples().catch<SampleIncident[]>(() => []),
    api.integrations().catch<IntegrationStatus[]>(() => []),
    api.health().catch<HealthResponse>(() => ({
      status: "unknown",
      bedrock_enabled: false,
      model: "demo",
    })),
    api.recent(1).catch<IncidentSummary[]>(() => []),
  ]);

  const connectedCount = integrations.filter((i) => i.connected).length;
  const totalIntegrations = integrations.length;

  return (
    <section className="mx-auto max-w-7xl px-4 sm:px-6 py-6 sm:py-10">
      <header className="mb-6 sm:mb-7 flex items-start justify-between gap-4 sm:gap-6 flex-wrap">
        <div className="min-w-0">
          <nav className="flex items-center gap-1.5 text-[11.5px] text-ink-400 font-medium">
            <Link href="/" className="hover:text-ink-50 transition">
              IncidentIQ
            </Link>
            <span className="text-ink-700">/</span>
            <span className="text-ink-200">Dashboard</span>
          </nav>
          <h1 className="mt-3 text-2xl sm:text-3xl font-semibold tracking-tight text-ink-50">
            Analyze an incident
          </h1>
          <p className="mt-2 text-[13.5px] sm:text-base text-ink-300 max-w-2xl">
            Paste logs, upload a file, or pull straight from your connected
            monitoring stack. The agent returns a structured root-cause
            analysis in seconds — for whatever team / service / repo you
            point it at.{" "}
            <Link
              href="/settings"
              className="text-brand-300 hover:text-brand-200 underline decoration-brand-500/30 underline-offset-2"
            >
              Connect your stack →
            </Link>
          </p>
        </div>

        {/* Status rail. Reads as the small system-health bar a real
            operations tool would have in its header. */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* AI status. We never say "Demo mode" - it scares users away
              from a perfectly working installation that just happens to
              be missing AWS credentials. Three honest states:
                live      - Bedrock authenticated + reachable
                offline   - health endpoint replied but bedrock disabled
                unreachable - health endpoint itself failed (status==='unknown')
          */}
          <StatusPill
            tone={
              health.bedrock_enabled
                ? "live"
                : health.status === "unknown"
                  ? "warn"
                  : "neutral"
            }
            label={
              health.bedrock_enabled
                ? "AI online"
                : health.status === "unknown"
                  ? "Backend unreachable"
                  : "AI offline"
            }
            icon={<Cpu className="size-3" />}
          />
          <StatusPill
            tone={connectedCount > 0 ? "live" : "neutral"}
            label={
              totalIntegrations > 0
                ? `Integrations: ${connectedCount}/${totalIntegrations}`
                : "Integrations: -"
            }
          />
          {recent.length > 0 ? (
            <Link
              href="/incidents"
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium bg-white/[0.04] text-ink-200 border border-white/[0.07] hover:bg-white/[0.07] transition"
            >
              <HistoryIcon className="size-3" />
              Last: {recent[0].incident_id}
              <ArrowUpRight className="size-3" />
            </Link>
          ) : null}
        </div>
      </header>

      {/* Watch Mode card. Sits between the page header and the
          Analyze panel so it reads as a parallel action ("manually
          analyze a paste below, OR enable hands-off detection right
          here") instead of disappearing into the status-pill rail. */}
      <div className="mb-6">
        <WatchToggle />
      </div>

      <Suspense>
        <AnalyzePanel samples={samples} integrations={integrations} />
      </Suspense>

    </section>
  );
}

function StatusPill({
  tone,
  label,
  icon,
}: {
  tone: "live" | "warn" | "neutral";
  label: string;
  icon?: React.ReactNode;
}) {
  const styles =
    tone === "live"
      ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/25"
      : tone === "warn"
        ? "bg-amber-500/10 text-amber-300 border-amber-500/25"
        : "bg-white/[0.04] text-ink-200 border-white/[0.07]";

  const dot =
    tone === "live"
      ? "bg-emerald-400"
      : tone === "warn"
        ? "bg-amber-400"
        : "bg-ink-400";

  return (
    <span
      className={
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium border " +
        styles
      }
    >
      <span className={"size-1.5 rounded-full " + dot} />
      {icon}
      {label}
    </span>
  );
}
