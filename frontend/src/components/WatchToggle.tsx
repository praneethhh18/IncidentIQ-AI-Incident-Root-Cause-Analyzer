"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Loader2,
  Radar,
  RadioTower,
  Square,
  Sparkles,
} from "lucide-react";

import { api } from "@/lib/api";
import type { WatchStatusPayload } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Hands-off detection card. Reads as a proper feature CTA, not a tiny
 * status pill - judges should immediately understand this is a thing
 * they can turn on, not a label. When the background poller is
 * running we flip into a "watching" state with live counters.
 *
 * Polls /watch/status every 5s while running, so the operator sees
 * the last-polled timestamp tick and the auto-incident counter
 * advance without a page refresh.
 */
export function WatchToggle({
  onIncidentCreated,
}: {
  /** Fires once per detected new incident so the parent can refresh
   * its recent-incidents list. */
  onIncidentCreated?: (incidentId: string) => void;
}) {
  const [status, setStatus] = useState<WatchStatusPayload | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastSeenIncidentId = useRef<string | null>(null);

  const refresh = async () => {
    try {
      const next = await api.watchStatus();
      setStatus(next);
      if (
        next.last_incident_id &&
        next.last_incident_id !== lastSeenIncidentId.current
      ) {
        const previous = lastSeenIncidentId.current;
        lastSeenIncidentId.current = next.last_incident_id;
        if (previous !== null && onIncidentCreated) {
          onIncidentCreated(next.last_incident_id);
        }
      }
    } catch {
      /* status fetch is best-effort */
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (!status?.running) return;
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [status?.running]);

  const toggle = async () => {
    setBusy(true);
    setError(null);
    try {
      const next = status?.running
        ? await api.watchStop()
        : await api.watchStart({});
      setStatus(next);
      if (next.last_incident_id) {
        lastSeenIncidentId.current = next.last_incident_id;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const running = status?.running ?? false;
  const lastPolledRel = relativeTime(status?.last_polled_at);

  return (
    <div
      className={cn(
        "rounded-xl border px-4 sm:px-5 py-3.5 sm:py-4 flex items-center justify-between gap-4 flex-wrap transition",
        running
          ? "border-emerald-500/30 bg-emerald-500/[0.04]"
          : "border-white/[0.07] bg-white/[0.02] hover:bg-white/[0.04]",
      )}
    >
      <div className="flex items-start gap-3 min-w-0">
        <div
          className={cn(
            "shrink-0 size-9 rounded-lg grid place-items-center border",
            running
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-white/[0.08] bg-white/[0.04] text-ink-200",
          )}
        >
          {running ? (
            <RadioTower className="size-4" />
          ) : (
            <Radar className="size-4" />
          )}
        </div>

        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[13.5px] sm:text-[14px] font-semibold text-ink-50">
            {running ? "Watching production" : "Hands-off detection"}
            {running ? (
              <span className="inline-flex items-center gap-1 chip text-[10px] py-0 bg-emerald-500/15 text-emerald-200 border-emerald-500/30">
                <span className="size-1.5 rounded-full bg-emerald-400 animate-pulse" />
                live
              </span>
            ) : null}
          </div>
          <div className="text-[12px] text-ink-400 mt-0.5 leading-snug">
            {running ? (
              <>
                Polling Datadog every {status?.poll_interval_s ?? 60}s for new
                errors. Last polled {lastPolledRel}.{" "}
                <span className="text-emerald-200 font-medium">
                  {status?.incidents_created ?? 0} auto-incident
                  {(status?.incidents_created ?? 0) === 1 ? "" : "s"}
                </span>{" "}
                created since start.
              </>
            ) : (
              <>
                Turn this on and IncidentIQ auto-creates incidents whenever
                Datadog sees a fresh error cluster on{" "}
                <span className="text-ink-200">fashion-aura-api</span>. No
                manual analyze clicks.
              </>
            )}
          </div>
          {error ? (
            <div className="mt-1.5 text-[11.5px] text-red-300">{error}</div>
          ) : null}
        </div>
      </div>

      <button
        onClick={toggle}
        disabled={busy}
        className={cn(
          "shrink-0 inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-[13px] font-medium border transition",
          running
            ? "bg-white/[0.04] text-ink-200 border-white/[0.10] hover:bg-red-500/10 hover:text-red-200 hover:border-red-500/30"
            : "bg-brand-500/15 text-brand-100 border-brand-500/40 hover:bg-brand-500/25",
          busy && "opacity-60 cursor-wait",
        )}
        title={
          running
            ? "Stop the background poller"
            : "Start auto-polling Datadog for new errors"
        }
      >
        {busy ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : running ? (
          <Square className="size-3.5" />
        ) : (
          <Sparkles className="size-3.5" />
        )}
        {running ? "Stop watching" : "Start Watch Mode"}
        {!running && !busy ? (
          <ArrowRight className="size-3.5 -mr-1" />
        ) : null}
      </button>
    </div>
  );
}

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "(starting)";
  const t = new Date(iso).getTime();
  const diff = Math.max(0, Date.now() - t);
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return `${h}h ago`;
}
