import Link from "next/link";
import { ArrowRight, Check, Plug2, Plus, XCircle } from "lucide-react";
import type { IntegrationStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const ICONS: Record<string, string> = {
  Datadog: "🐶",
  "Grafana / Loki": "📊",
  "New Relic": "🟢",
};

/**
 * Friendlier subtitle than the bare "Not configured" the backend
 * returns. Frames unconfigured connectors as ready-to-enable rather
 * than missing features. Reads from the integration name so it stays
 * stable when we add Splunk, Honeycomb, etc.
 */
const SUBTITLE_WHEN_OFF: Record<string, string> = {
  Datadog: "Ready · sign in with Datadog API + App keys",
  "Grafana / Loki": "Ready · paste a Loki URL + access token to enable",
  "New Relic": "Ready · paste a User key + Account ID to enable",
};

/**
 * One-line "what we do with this" tagline so the cards explain
 * themselves even before the user signs in. Datadog is the live
 * reference connector; the others use the same protocol.
 */
const PURPOSE: Record<string, string> = {
  Datadog: "Pulls live logs via the Logs Search API.",
  "Grafana / Loki": "Pulls live logs via the Loki HTTP query API.",
  "New Relic": "Pulls live logs via the NRQL HTTP API.",
};

export function IntegrationCard({ status }: { status: IntegrationStatus }) {
  const stateClass = status.connected
    ? "border-emerald-500/30 bg-emerald-500/5"
    : status.enabled
    ? "border-amber-500/30 bg-amber-500/5"
    : "border-white/[0.06] bg-ink-900/40";

  const subtitle = status.connected
    ? "Connected"
    : status.enabled
    ? "Configured · not reachable"
    : SUBTITLE_WHEN_OFF[status.name] ?? "Available · paste credentials to enable";

  return (
    <div
      className={cn(
        "rounded-2xl border p-4 transition hover:bg-ink-900/70",
        stateClass,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="size-9 grid place-items-center rounded-lg bg-white/[0.05] border border-white/[0.06] text-base">
            {ICONS[status.name] ?? <Plug2 className="size-4 text-ink-400" />}
          </div>
          <div>
            <div className="font-medium text-ink-50 text-sm">{status.name}</div>
            <div className="text-[11px] text-ink-500 mt-0.5">{subtitle}</div>
          </div>
        </div>
        <StatusPill status={status} />
      </div>
      {PURPOSE[status.name] ? (
        <div className="mt-3 text-[11.5px] text-ink-300 leading-snug">
          {PURPOSE[status.name]}
        </div>
      ) : null}
      {status.detail ? (
        <div className="mt-1.5 text-[11px] text-ink-500 leading-snug">
          {status.detail}
        </div>
      ) : null}
      {!status.connected ? (
        <Link
          href="/settings"
          className="mt-2 inline-flex items-center gap-1 text-[11.5px] font-medium text-brand-300 hover:text-brand-200 transition"
        >
          Connect <ArrowRight className="size-3" />
        </Link>
      ) : null}
    </div>
  );
}

function StatusPill({ status }: { status: IntegrationStatus }) {
  if (status.connected) {
    return (
      <span className="chip bg-emerald-500/15 text-emerald-300 border-emerald-500/30">
        <Check className="size-3" /> live
      </span>
    );
  }
  if (status.enabled) {
    return (
      <span className="chip bg-amber-500/15 text-amber-300 border-amber-500/30">
        <XCircle className="size-3" /> error
      </span>
    );
  }
  // 'Available' reads as a feature waiting on credentials rather than
  // a missing capability. Datadog/Grafana/NR are all first-class here.
  return (
    <span className="chip bg-white/[0.04] text-ink-300 border-white/[0.08]">
      <Plus className="size-3" /> Available
    </span>
  );
}
