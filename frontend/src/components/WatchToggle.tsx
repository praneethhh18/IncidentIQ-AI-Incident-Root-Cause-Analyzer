"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, Radar, RadioTower } from "lucide-react";

import { api } from "@/lib/api";
import type { WatchStatusPayload } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Status pill + on/off control for Watch Mode. When the backend
 * watcher is running we poll its status every 5 seconds so the user
 * sees the last-polled timestamp tick and the auto-incident counter
 * advance without a page refresh.
 *
 * Mounting this on the dashboard surface gives the demo its "I
 * haven't touched the keyboard and an incident just appeared"
 * moment - the recent-incidents list updates because the watcher
 * persisted a new analysis to the same store.
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
    <div className="inline-flex items-center gap-2">
      <button
        onClick={toggle}
        disabled={busy}
        title={running ? "Stop auto-polling Datadog" : "Auto-poll Datadog for new errors"}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium border transition",
          running
            ? "bg-emerald-500/10 text-emerald-200 border-emerald-500/25 hover:bg-emerald-500/15"
            : "bg-white/[0.04] text-ink-200 border-white/[0.07] hover:bg-white/[0.07]",
          busy && "opacity-60",
        )}
      >
        {busy ? (
          <Loader2 className="size-3 animate-spin" />
        ) : running ? (
          <RadioTower className="size-3" />
        ) : (
          <Radar className="size-3" />
        )}
        {running ? "Watching production" : "Start Watch Mode"}
      </button>

      {running && status ? (
        <span className="text-[10.5px] text-ink-500 font-mono tabular-nums">
          polled {lastPolledRel} · {status.incidents_created} auto-incidents
        </span>
      ) : null}

      {error ? (
        <span className="text-[10.5px] text-red-300">{error}</span>
      ) : null}
    </div>
  );
}

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  const diff = Math.max(0, Date.now() - t);
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return `${h}h ago`;
}
