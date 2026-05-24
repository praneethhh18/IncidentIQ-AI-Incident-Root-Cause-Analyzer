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
import { ComingSoonIntegrations } from "@/components/ComingSoonIntegrations";

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
    <section className="mx-auto max-w-7xl px-6 py-10">
      <header className="mb-7 flex items-start justify-between gap-6 flex-wrap">
        <div>
          <nav className="flex items-center gap-1.5 text-[11.5px] text-ink-400 font-medium">
            <Link href="/" className="hover:text-ink-50 transition">
              IncidentIQ
            </Link>
            <span className="text-ink-700">/</span>
            <span className="text-ink-200">Dashboard</span>
          </nav>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-ink-50">
            Analyze an incident
          </h1>
          <p className="mt-2 text-ink-300 max-w-2xl">
            Paste logs, upload a file, or pull straight from a connected
            monitoring tool. The agent returns a structured analysis in seconds.
          </p>
        </div>

        {/* Status rail. Reads as the small system-health bar a real
            operations tool would have in its header. */}
        <div className="flex items-center gap-2 flex-wrap">
          <StatusPill
            tone={health.bedrock_enabled ? "live" : "demo"}
            label={health.bedrock_enabled ? "AI online" : "Demo mode"}
            icon={<Cpu className="size-3" />}
          />
          <StatusPill
            tone={connectedCount > 0 ? "live" : "neutral"}
            label={`Integrations: ${connectedCount}/${totalIntegrations}`}
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

      <Suspense>
        <AnalyzePanel samples={samples} integrations={integrations} />
      </Suspense>

      <ComingSoonIntegrations />
    </section>
  );
}

function StatusPill({
  tone,
  label,
  icon,
}: {
  tone: "live" | "demo" | "neutral";
  label: string;
  icon?: React.ReactNode;
}) {
  const styles =
    tone === "live"
      ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/25"
      : tone === "demo"
      ? "bg-amber-500/10 text-amber-300 border-amber-500/25"
      : "bg-white/[0.04] text-ink-200 border-white/[0.07]";

  const dot =
    tone === "live"
      ? "bg-emerald-400"
      : tone === "demo"
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
